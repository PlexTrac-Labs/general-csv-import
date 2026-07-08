#!/usr/bin/env python3
"""Generate large, customizable CSV files for performance/memory testing of the
General CSV Import parser.

The generated CSV always has the same 10 columns (chosen so row math is easy to
reason about during testing):

    1. client_name        2. report_name      3. finding_title
    4. description         5. severity         6. status
    7. recommendations     8. references       9. asset_name
   10. asset_port

These map onto Plextrac keys via the companion file
``scripts/perf_memory_testing/test_csv_header_mapping.csv``. Point ``headers_file_path`` (config.yaml)
at that mapping and ``data_file_path`` at the CSV this script produces.

The data model (why row count != finding count)
------------------------------------------------
A CSV row is a (finding, affected-asset) PAIR. So a finding affecting A assets
produces A rows that share identical finding fields (title/description/severity/
status/recommendations/references) and differ only in asset_name/asset_port.
Assets are drawn from a per-report POOL of distinct assets (P), reused across
findings, so distinct assets are far fewer than rows - and fewer than findings.

    Client                           C
     └─ Report            (ptrac)    C*R          <- fan-out / ptrac files
         ├─ Finding (distinct)       C*R*F        <- objects to create
         │    └─ affects A assets  -> A rows      <- rows = C*R*F*A
         └─ Asset pool (distinct)    C*R*P        <- dedup-map size (P < F)

    rows            = C * R * F * A
    reports/ptracs  = C * R
    distinct finds  = C * R * F
    distinct assets = C * R * P
    asset reuse     = F * A / P     (avg times each asset is referenced)

Auto-solving the shape from a row target ("area for a given perimeter")
-----------------------------------------------------------------------
Each dimension stresses a different parser subsystem (open ptrac buffers, per-
report object volume, asset-dedup churn, top-level grouping). A degenerate
factoring of N pegs one axis and zeroes the others, so it can pass even when a
different axis would OOM. The solver distributes the row budget GEOMETRICALLY
across whichever dimensions you did not pin, keeping the shape as balanced
(square) as possible - that maximizes coverage across all axes at once.

Reference cell (at 100k rows): C=10, R=25, F=100, A=4, P=40 (= 0.4*F).
Per-client cell = R*F*A = 10,000 rows, so the 100k target solves to exactly
10 x 25 x 100 x 4 with 40 distinct assets/report (~10x reuse).

  --auto balanced  (default)  grow C,R,F,A together as N^(1/4).
  --auto linear               lock R,F,A; grow only clients (max fan-out).

Any of --clients/--reports-per-client/--findings-per-report/--assets-per-finding
you pass is locked; the solver fills in the rest to hit --rows.

Examples
--------
  # Auto-shape 1M rows (balanced), write grouped CSV
  python scripts/perf_memory_testing/generate_test_csv.py --rows 1_000_000 -o testing_files/perf/data_1m.csv

  # Same volume but scatter reports so every ptrac stays open (max memory)
  python scripts/perf_memory_testing/generate_test_csv.py --rows 1_000_000 --layout interleaved \
      -o testing_files/perf/data_1m_il.csv

  # Pin the shape explicitly (your worked example)
  python scripts/perf_memory_testing/generate_test_csv.py --clients 10 --reports-per-client 25 \
      --findings-per-report 100 --assets-per-finding 4 -o testing_files/perf/data.csv

  # Cap by size: stop at ~2 GB, pad rows to widen them
  python scripts/perf_memory_testing/generate_test_csv.py --rows 15_000_000 --target-size-mb 2048 \
      --pad-bytes 300 -o testing_files/perf/data_2gb.csv
"""

import argparse
import csv
import math
import os
import sys
import time

# Hard safety ceilings: stop at whichever comes first. The byte ceiling sits
# above a default-width 15M-row file (~4.8 GB) so the top row-step always
# completes; it still backstops padded / runaway runs.
DEFAULT_MAX_ROWS = 15_000_000
DEFAULT_MAX_BYTES = 6 * 1024 * 1024 * 1024  # 6 GiB

# Absolute ceiling that ALWAYS applies, even with --ignore-byte-cap. This is the
# last line of defense against filling the disk. The only way past it is to edit
# this value in the source - deliberately, not via a CLI flag.
ABSOLUTE_MAX_BYTES = 50 * 1024 * 1024 * 1024  # 50 GiB

# Rough per-row size (bytes) used only for the pre-run size estimate shown before
# the --ignore-byte-cap confirmation prompt. Measured ~315 B/row at default width.
EST_BYTES_PER_ROW = 320

# The 10 source column headers written as the first row of the data CSV.
# These must match row 1 of scripts/perf_memory_testing/test_csv_header_mapping.csv exactly.
COLUMNS = [
    "client_name", "report_name", "finding_title", "description", "severity",
    "status", "recommendations", "references", "asset_name", "asset_port",
]

SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]
STATUSES = ["Open", "In Process", "Closed"]

# Reference shape at this row count; the solver scales relative to it.
REF = {"C": 10, "R": 25, "F": 100, "A": 4}
REF_ROWS = REF["C"] * REF["R"] * REF["F"] * REF["A"]  # 100,000
ASSET_POOL_RATIO = 0.4  # distinct assets/report = ratio * findings/report (P < F)

# How often (in rows) to check on-disk byte size and print progress.
# Smaller = tighter byte-cap precision; large enough to keep throughput high.
CHECK_EVERY = 10_000


# --------------------------------------------------------------------------- #
# Shape solver
# --------------------------------------------------------------------------- #
def solve_shape(target_rows, fixed, mode):
    """Return (C, R, F, A) hitting ~target_rows, honoring any fixed dims.

    `fixed` is a dict subset of {'C','R','F','A'} the user pinned. `mode` selects
    which dims are allowed to move: linear -> {C}; balanced -> {C,R,F,A};
    manual -> {C,R,F,A}. Free dims are scaled geometrically
    from REF so the shape stays balanced, then C is finalized to land on target.
    """
    allowed = {
        "linear": {"C"},
        "balanced": {"C", "R", "F", "A"},
        "manual": {"C", "R", "F", "A"},
    }[mode]

    val = dict(REF)
    val.update(fixed)
    free = [d for d in ("C", "R", "F", "A") if d in allowed and d not in fixed]

    if free:
        fixed_product = math.prod(val[d] for d in ("C", "R", "F", "A") if d not in free)
        ref_free_product = math.prod(REF[d] for d in free)
        scale = (target_rows / (fixed_product * ref_free_product)) ** (1.0 / len(free))
        for d in free:
            val[d] = max(1, round(REF[d] * scale))
        # Clients are the coarsest knob: finalize C to best match the target.
        if "C" in free:
            val["C"] = max(1, round(target_rows / (val["R"] * val["F"] * val["A"])))

    return val["C"], val["R"], val["F"], val["A"]


def resolve_pool(F, A, pool_override, pool_ratio):
    """Distinct assets per report. Default keeps P < F (reuse); always >= A."""
    P = pool_override if pool_override else round(F * pool_ratio)
    return max(A, min(P, F))  # need >= A to sample A; cap at F


# --------------------------------------------------------------------------- #
# Row builders (all deterministic from indices -> reproducible, easy to verify)
# --------------------------------------------------------------------------- #
def client_name(c):
    return f"Client {c:05d}"


def report_name(c, r):
    return f"Report {c:05d}-{r:04d}"


def finding_fields(c, r, fi, gf, pad):
    """First 8 columns for a finding (client..references)."""
    sev = SEVERITIES[gf % len(SEVERITIES)]
    stat = STATUSES[gf % len(STATUSES)]
    desc = (
        f"Synthetic finding {gf}: client={c} report={r} finding={fi}. "
        f"Generated for performance testing."
    )
    if pad:
        desc = desc + " " + ("x" * pad)
    return [
        client_name(c),
        report_name(c, r),
        f"Finding {gf} - {sev} issue",
        desc,
        sev,
        stat,
        f"Remediate finding {gf}: apply the recommended fix and re-test.",
        f"https://example.test/ref/{gf} | CWE-{(gf % 999) + 1}",
    ]


def asset_fields(c, r, k):
    """Last 2 columns for asset pool member k of report (c, r)."""
    name = f"asset-{c:05d}-{r:04d}-{k:05d}.example.test"
    port = str(1024 + ((c * 100003 + r * 1009 + k) % 64511))
    return [name, port]


def iter_rows(C, R, F, A, P, layout, fo_per, ao_per, pad):
    """Yield row-lists. Constant memory: nothing is buffered.

    grouped:     all rows of a report are contiguous (a finding's A asset-rows
                 together), realistic sorted export.
    interleaved: findings are emitted round-robin across every report, so reports
                 are scattered through the whole file and the parser must keep
                 every ptrac open at once. Worst case for memory.
    """
    if layout == "interleaved":
        # Type-variant extras need per-report bookkeeping that defeats the point
        # of interleaving; keep this layout to the pure (finding,asset) stress.
        if fo_per or ao_per:
            raise ValueError(
                "finding-only / asset-only rows are only supported with "
                "--layout grouped"
            )
        num_reports = C * R
        for fi in range(F):
            for rep in range(num_reports):
                c, r = divmod(rep, R)
                gf = rep * F + fi
                ff = finding_fields(c, r, fi, gf, pad)
                for j in range(A):
                    k = (fi * A + j) % P
                    yield ff + asset_fields(c, r, k)
        return

    # grouped
    for c in range(C):
        for r in range(R):
            base_f = (c * R + r) * F
            for fi in range(F):
                gf = base_f + fi
                ff = finding_fields(c, r, fi, gf, pad)
                for j in range(A):
                    k = (fi * A + j) % P
                    yield ff + asset_fields(c, r, k)
            # finding-only rows: finding present, no asset
            for x in range(fo_per):
                gf = base_f + F + x
                yield finding_fields(c, r, F + x, gf, pad) + ["", ""]
            # asset-only rows: asset present, no finding
            for x in range(ao_per):
                yield [client_name(c), report_name(c, r), "", "", "", "", "", ""] \
                    + asset_fields(c, r, x % P)


# --------------------------------------------------------------------------- #
# CLI / driver
# --------------------------------------------------------------------------- #
def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024


def parse_int(value):
    """Accept underscores/commas, e.g. 20_000_000 or 20,000,000."""
    return int(str(value).replace("_", "").replace(",", ""))


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Generate large customizable test CSVs for the CSV import parser.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--rows", type=parse_int, default=100_000,
                   help="Target data rows. The solver shapes the hierarchy to hit this.")
    p.add_argument("--auto", choices=["balanced", "linear"], default="balanced",
                   help="balanced: grow C,R,F,A together. linear: grow only clients.")
    p.add_argument("--output", "-o", default="testing_files/perf/generated_test.csv",
                   help="Output CSV path. Parent dirs are created if missing.")

    # Dimension pins (any provided value is locked; the solver fills the rest).
    p.add_argument("--clients", type=parse_int, default=None, help="Pin client count (C).")
    p.add_argument("--reports-per-client", type=parse_int, default=None,
                   help="Pin reports per client (R). C*R = total ptrac files.")
    p.add_argument("--findings-per-report", type=parse_int, default=None,
                   help="Pin distinct findings per report (F).")
    p.add_argument("--assets-per-finding", type=parse_int, default=None,
                   help="Pin affected assets per finding (A). A rows per finding.")
    p.add_argument("--assets-per-report", type=parse_int, default=None,
                   help="Pin distinct asset pool per report (P). Default = ratio*F.")
    p.add_argument("--asset-pool-ratio", type=float, default=ASSET_POOL_RATIO,
                   help="P as a fraction of F when --assets-per-report is unset.")

    # Row-type mix (parser branches on finding/asset/both). Default 0 = all 'both'.
    p.add_argument("--finding-only-per-report", type=parse_int, default=0,
                   help="Extra findings per report with no asset (grouped only).")
    p.add_argument("--asset-only-per-report", type=parse_int, default=0,
                   help="Extra asset-only rows per report, no finding (grouped only).")

    p.add_argument("--layout", choices=["grouped", "interleaved"], default="grouped",
                   help="grouped: report rows contiguous. interleaved: scattered (max memory).")
    p.add_argument("--pad-bytes", type=parse_int, default=0,
                   help="Extra bytes appended to each description to widen rows.")
    p.add_argument("--target-size-mb", type=float, default=None,
                   help="Stop once the file reaches this size (MB). Tightens the 6 GiB ceiling.")
    p.add_argument("--max-rows", type=parse_int, default=DEFAULT_MAX_ROWS,
                   help="Hard row ceiling regardless of the solved shape.")
    p.add_argument("--max-bytes", type=parse_int, default=DEFAULT_MAX_BYTES,
                   help="Hard byte ceiling regardless of the solved shape.")
    p.add_argument("--ignore-byte-cap", action="store_true",
                   help="Disable the --max-bytes ceiling (still bounded by the "
                        "in-code ABSOLUTE_MAX_BYTES). Prints an estimated size and "
                        "requires interactive confirmation before generating.")
    args = p.parse_args(argv)

    fixed = {}
    if args.clients is not None:
        fixed["C"] = args.clients
    if args.reports_per_client is not None:
        fixed["R"] = args.reports_per_client
    if args.findings_per_report is not None:
        fixed["F"] = args.findings_per_report
    if args.assets_per_finding is not None:
        fixed["A"] = args.assets_per_finding

    # If every dim is pinned the solver just echoes them and --rows is advisory.
    all_pinned = {"C", "R", "F", "A"}.issubset(fixed)
    C, R, F, A = solve_shape(args.rows, fixed, args.auto)
    P = resolve_pool(F, A, args.assets_per_report, args.asset_pool_ratio)

    fo = args.finding_only_per_report
    ao = args.asset_only_per_report
    if args.layout == "interleaved" and (fo or ao):
        p.error("--finding-only-per-report / --asset-only-per-report require "
                "--layout grouped")
    rows_per_report = F * A + fo + ao
    total_rows = C * R * rows_per_report

    row_cap = min(total_rows, args.max_rows)
    if args.ignore_byte_cap:
        byte_cap = ABSOLUTE_MAX_BYTES
        byte_cap_label = f"{human_bytes(byte_cap)} (in-code absolute ceiling)"
    else:
        byte_cap = args.max_bytes
        byte_cap_label = human_bytes(byte_cap)
    if args.target_size_mb is not None:
        byte_cap = min(byte_cap, int(args.target_size_mb * 1024 * 1024))
        byte_cap_label = f"{human_bytes(byte_cap)} (--target-size-mb)"

    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    reuse = (F * A) / P
    print(f"Generating CSV -> {out_path}")
    if all_pinned:
        print(f"  shape          : pinned ({args.auto} solver bypassed)")
    else:
        print(f"  target rows    : {args.rows:,}  (auto: {args.auto})")
    print(f"  clients (C)    : {C:,}")
    print(f"  reports/client : {R:,}")
    print(f"  findings/report: {F:,}")
    print(f"  assets/finding : {A:,}")
    print(f"  asset pool/rpt : {P:,}  (reuse ~{reuse:.1f}x per asset)")
    if fo or ao:
        print(f"  +finding-only  : {fo}/report   +asset-only: {ao}/report")
    print("  " + "-" * 56)
    print(f"  reports/ptracs : {C * R:,}")
    print(f"  distinct finds : {C * R * (F + fo):,}")
    print(f"  distinct assets: {C * R * P:,}")
    print(f"  projected rows : {total_rows:,}")
    print(f"  byte ceiling   : {byte_cap_label}")
    print(f"  layout         : {args.layout}   pad-bytes/row: {args.pad_bytes}")
    print("-" * 60)

    # --ignore-byte-cap lifts the soft ceiling, so estimate the size and make the
    # user confirm. The in-code ABSOLUTE_MAX_BYTES still bounds generation.
    if args.ignore_byte_cap:
        est_rows = min(total_rows, row_cap)
        bytes_per_row = EST_BYTES_PER_ROW + args.pad_bytes
        est_bytes = est_rows * bytes_per_row
        truncates = est_bytes > byte_cap
        print(f"--ignore-byte-cap: soft --max-bytes ceiling disabled.")
        print(f"  estimated output: ~{human_bytes(min(est_bytes, byte_cap))} for "
              f"~{est_rows:,} rows (~{bytes_per_row} B/row).")
        if truncates:
            print(f"  WARNING: estimate exceeds the in-code absolute ceiling "
                  f"({human_bytes(ABSOLUTE_MAX_BYTES)}); output will STOP there.")
            print(f"  To go higher, edit ABSOLUTE_MAX_BYTES in {os.path.basename(__file__)}.")
        try:
            resp = input("  Proceed? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted (no confirmation received).")
            return 1
        if resp not in ("y", "yes"):
            print("Aborted.")
            return 1
        print("-" * 60)

    start = time.time()
    written = 0
    size_capped = False

    with open(out_path, "w", newline="", encoding="utf-8", buffering=1024 * 1024) as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)

        for row in iter_rows(C, R, F, A, P, args.layout, fo, ao, args.pad_bytes):
            writer.writerow(row)
            written += 1
            if written >= row_cap:
                break
            if written % CHECK_EVERY == 0:
                f.flush()
                size = f.tell()
                elapsed = time.time() - start
                rate = written / elapsed if elapsed else 0
                print(f"  {written:,} rows  {human_bytes(size)}  {rate:,.0f} rows/s",
                      end="\r", flush=True)
                if size >= byte_cap:
                    size_capped = True
                    break

        f.flush()
        final_size = f.tell()

    elapsed = time.time() - start
    print(" " * 80, end="\r")
    print("-" * 60)
    print(f"Done in {elapsed:.1f}s")
    print(f"  rows written : {written:,}")
    print(f"  file size    : {human_bytes(final_size)}")
    if size_capped:
        print(f"  NOTE: stopped early - hit byte ceiling ({human_bytes(byte_cap)}).")
    elif written < total_rows:
        print(f"  NOTE: stopped early - hit row ceiling ({row_cap:,}).")
    print(f"  header map   : scripts/perf_memory_testing/test_csv_header_mapping.csv")


if __name__ == "__main__":
    sys.exit(main())
