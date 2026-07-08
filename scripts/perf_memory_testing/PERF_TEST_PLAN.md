# CSV Import — Performance / Memory Test Plan

Test corpus for finding the memory bottleneck when a single CSV is parsed and
fanned out into many `.ptrac` files. All files are produced by
`[generate_test_csv.py](generate_test_csv.py)` and mapped with
`[test_csv_header_mapping.csv](test_csv_header_mapping.csv)`.

## The data model (why row count != finding count)

A CSV row is a **(finding, affected-asset) pair**. A finding affecting `A` assets
emits `A` rows that share identical finding fields and differ only in
`asset_name` / `asset_port`. Assets come from a per-report **pool** (`P`) that is
reused across findings, so distinct assets are far fewer than rows — and fewer
than findings.

```
Client                           C
 └─ Report            (ptrac)    C·R          <- fan-out / ptrac files
     ├─ Finding (distinct)       C·R·F        <- objects to create
     │    └─ affects A assets  -> A rows      <- rows = C·R·F·A
     └─ Asset pool (distinct)    C·R·P        <- dedup-map size (P < F)

 rows            = C·R·F·A          asset reuse = F·A / P
 reports/ptracs  = C·R             distinct finds = C·R·F
 distinct assets = C·R·P
```

**Reference cell (100k rows):** `C=10, R=25, F=100, A=4, P=40` → 250 ptracs,
25k findings, 10k assets, ~10× asset reuse. Every scaling strategy below grows
out from this cell.

## What each dimension stresses


| Dimension                          | Parser subsystem under pressure                              |
| ---------------------------------- | ------------------------------------------------------------ |
| reports `C·R`                      | number of ptrac buffers held open / flushed (fan-out memory) |
| findings/report `F`                | per-ptrac object volume                                      |
| assets/finding `A` + reuse `F·A/P` | asset-dedup map churn                                        |
| clients `C`                        | top-level grouping                                           |


A lopsided file pegs one axis and zeroes the others, so it can pass even when a
different axis would OOM. The two **auto modes** and the two **single-axis
sweeps** below cover every axis deliberately.

---

## The corpus — 17 files

All write to `testing_files/perf/` (gitignored). `~size` assumes the default row
width (~315 bytes/row); add `--pad-bytes N` to widen.

> **Why 15M is the top step.** A reasonable real-world worst case is
> **400 clients × 4 reports/year × 4 years × 150 findings/report × 15 assets/finding
> = 14.4M rows** (4.5 GB). The 15M step sits just above that. The script's safety
> ceilings are set to **15M rows / 6 GiB** so a default-width 15M file (4.7 GB) always completes.

**Going past 6 GiB.** There are three tiers of byte protection:

1. **Soft ceiling** (`--max-bytes`, default 6 GiB) — stops generation, no prompt.
2. `**--ignore-byte-cap`** — lifts the soft ceiling, prints an estimated final
  size, and **requires an interactive `y/N` confirmation** before writing.
3. **Absolute ceiling** (`ABSOLUTE_MAX_BYTES`, 50 GiB in code) — always applies,
  even with `--ignore-byte-cap`. The only way past it is editing that constant
   in `[generate_test_csv.py](generate_test_csv.py)` — deliberately, not via a flag.

```bash
# e.g. a padded 15M file larger than 6 GiB — prompts for confirmation
python scripts/perf_memory_testing/generate_test_csv.py --rows 15000000 --pad-bytes 400 \
    --ignore-byte-cap -o testing_files/perf/big.csv
```

### Shared reference (100k)

At 100k, balanced / linear / F-sweep / A-sweep are the *same shape*, so one file
serves all four. It's the baseline every larger file is compared against.


| File           | C × R × F × A     | Pool/reuse | ptracs | Finds  | Assets | ~Size |
| -------------- | ----------------- | ---------- | ------ | ------ | ------ | ----- |
| `ref_100k.csv` | 10 × 25 × 100 × 4 | 40 / 10×   | 250    | 25,000 | 10,000 | 30 MB |


```bash
python scripts/perf_memory_testing/generate_test_csv.py --rows 100000 -o testing_files/perf/ref_100k.csv
```

### A1 — Balanced (grow C, R, F, A together as N^¼)

Realistic all-axes growth; every dimension stays in a plausible range. **Use this
to answer "does the parser hold up as a real customer's data grows."**


| File           | C × R × F × A      | Pool/reuse  | ptracs | Finds   | Assets  | ~Size  |
| -------------- | ------------------ | ----------- | ------ | ------- | ------- | ------ |
| `bal_500k.csv` | 15 × 37 × 150 × 6  | 60 / 15×    | 555    | 83,250  | 33,300  | 150 MB |
| `bal_1m.csv`   | 18 × 44 × 178 × 7  | 71 / 17.5×  | 792    | 140,976 | 56,232  | 295 MB |
| `bal_5m.csv`   | 26 × 66 × 266 × 11 | 106 / 27.6× | 1,716  | 456,456 | 181,896 | 1.5 GB |
| `bal_15m.csv`  | 35 × 87 × 350 × 14 | 140 / 35×   | 3,045  | 1.07M   | 426,300 | 4.7 GB |


```bash
python scripts/perf_memory_testing/generate_test_csv.py --rows 500000   -o testing_files/perf/bal_500k.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 1000000  -o testing_files/perf/bal_1m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 5000000  -o testing_files/perf/bal_5m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 15000000 -o testing_files/perf/bal_15m.csv
```

### A2 — Linear (grow clients only → max ptrac fan-out)

Holds the report shape at reference and only adds clients. **This is the
"years-of-data fans out into tens of thousands of ptracs" stress** — isolates the
fan-out / open-buffer axis. At 15M it produces **37,500 ptracs**.

Growing Clients is the same as growing Reports, which is the more common real world usecase.


| File           | C × R × F × A       | Pool/reuse | ptracs     | Finds   | Assets  | ~Size  |
| -------------- | ------------------- | ---------- | ---------- | ------- | ------- | ------ |
| `lin_500k.csv` | 50 × 25 × 100 × 4   | 40 / 10×   | 1,250      | 125,000 | 50,000  | 150 MB |
| `lin_1m.csv`   | 100 × 25 × 100 × 4  | 40 / 10×   | 2,500      | 250,000 | 100,000 | 300 MB |
| `lin_5m.csv`   | 500 × 25 × 100 × 4  | 40 / 10×   | 12,500     | 1.25M   | 500,000 | 1.5 GB |
| `lin_15m.csv`  | 1500 × 25 × 100 × 4 | 40 / 10×   | **37,500** | 3.75M   | 1.5M    | 4.7 GB |


```bash
python scripts/perf_memory_testing/generate_test_csv.py --rows 500000   --auto linear -o testing_files/perf/lin_500k.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 1000000  --auto linear -o testing_files/perf/lin_1m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 5000000  --auto linear -o testing_files/perf/lin_5m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 15000000 --auto linear -o testing_files/perf/lin_15m.csv
```

### B1 — Findings-per-report sweep (pin C, R, A → grow F)

ptracs stay flat at 250; each ptrac gets heavier. **Isolates per-ptrac object
volume** — finds the point where a single report is too big to build in memory.


| File              | C × R × F × A       | Pool/reuse  | ptracs | Finds   | Assets  | ~Size  |
| ----------------- | ------------------- | ----------- | ------ | ------- | ------- | ------ |
| `fsweep_500k.csv` | 10 × 25 × 500 × 4   | 200 / 10×   | 250    | 125,000 | 50,000  | 150 MB |
| `fsweep_1m.csv`   | 10 × 25 × 1000 × 4  | 400 / 10×   | 250    | 250,000 | 100,000 | 300 MB |
| `fsweep_5m.csv`   | 10 × 25 × 5000 × 4  | 2,000 / 10× | 250    | 1.25M   | 500,000 | 1.5 GB |
| `fsweep_15m.csv`  | 10 × 25 × 15000 × 4 | 6,000 / 10× | 250    | 3.75M   | 1.5M    | 4.7 GB |


```bash
python scripts/perf_memory_testing/generate_test_csv.py --rows 500000   --clients 10 --reports-per-client 25 --assets-per-finding 4 -o testing_files/perf/fsweep_500k.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 1000000  --clients 10 --reports-per-client 25 --assets-per-finding 4 -o testing_files/perf/fsweep_1m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 5000000  --clients 10 --reports-per-client 25 --assets-per-finding 4 -o testing_files/perf/fsweep_5m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 15000000 --clients 10 --reports-per-client 25 --assets-per-finding 4 -o testing_files/perf/fsweep_15m.csv
```

### B2 — Assets-per-finding sweep (pin C, R, F → grow A)

ptracs and finding count stay flat; each finding fans out onto more assets and
**asset reuse climbs to 100×**. Isolates the asset-dedup map (how many times the
same asset is re-seen and matched).


| File              | C × R × F × A       | Pool/reuse | ptracs | Finds  | Assets  | ~Size  |
| ----------------- | ------------------- | ---------- | ------ | ------ | ------- | ------ |
| `asweep_500k.csv` | 10 × 25 × 100 × 20  | 40 / 50×   | 250    | 25,000 | 10,000  | 150 MB |
| `asweep_1m.csv`   | 10 × 25 × 100 × 40  | 40 / 100×  | 250    | 25,000 | 10,000  | 300 MB |
| `asweep_5m.csv`   | 10 × 25 × 100 × 200 | 200 / 100× | 250    | 25,000 | 50,000  | 1.5 GB |
| `asweep_15m.csv`  | 10 × 25 × 100 × 600 | 600 / 100× | 250    | 25,000 | 150,000 | 4.7 GB |


```bash
python scripts/perf_memory_testing/generate_test_csv.py --rows 500000   --clients 10 --reports-per-client 25 --findings-per-report 100 -o testing_files/perf/asweep_500k.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 1000000  --clients 10 --reports-per-client 25 --findings-per-report 100 -o testing_files/perf/asweep_1m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 5000000  --clients 10 --reports-per-client 25 --findings-per-report 100 -o testing_files/perf/asweep_5m.csv
python scripts/perf_memory_testing/generate_test_csv.py --rows 15000000 --clients 10 --reports-per-client 25 --findings-per-report 100 -o testing_files/perf/asweep_15m.csv
```

> Note on B2 at scale: once `A` exceeds the default pool (40), the pool grows with
> `A` (a finding can't hit the same asset twice), so at 15M the pool is 600 and
> distinct assets jump to 150k. That's expected — it's the extreme asset-fan-out
> case, not a realistic shape.

---

## Layout: grouped vs interleaved (not generated yet)

Every file above uses the default `**grouped**` layout: all rows for a
`(client, report)` are contiguous, like a sorted export. A streaming parser can
close and flush each ptrac as its group ends, so peak memory ≈ one report.

The orthogonal `**interleaved**` layout scatters every report's rows round-robin
through the whole file, so the parser must keep **every ptrac open
simultaneously** — peak memory ≈ the entire file's group structure. This is the
true memory worst case and is where a fan-out-into-hundreds-of-ptracs design
actually breaks.

Interleaving is deliberately left out of this first corpus to keep the variable
count down: establish the baseline ceiling on grouped data first, identify which
axis breaks, then re-generate **only that breaking case** with `--layout interleaved` to measure the real ceiling. Add the flag to any command above:

```bash
# worst-case memory version of a chosen run
python scripts/perf_memory_testing/generate_test_csv.py --rows 1000000 --layout interleaved \
    -o testing_files/perf/bal_1m_interleaved.csv
```

The nastiest single run in the whole matrix will be **linear 15M + interleaved** (37,500 ptracs, all held open at once).

> `--layout interleaved` is incompatible with the `--finding-only-per-report` /
> `--asset-only-per-report` row-type knobs (those are grouped-only).

---

## Running an import against a generated file

Point the config at the generated CSV and the shared mapping, then run the
parser:

```yaml
# config.yaml
headers_file_path: scripts/perf_memory_testing/test_csv_header_mapping.csv
data_file_path: testing_files/perf/bal_1m.csv
```

Suggested order: start with `ref_100k`, walk the **B sweeps** to find the axis
that breaks first, confirm the trend with **A (linear vs balanced)** at that
scale, then re-run that one case interleaved for the true ceiling.

---

## Runtime tracking (timing + memory)

Set `track_performance = True` in `[settings.py](../../settings.py)` to instrument
the import. All perf output goes to a **dedicated file** (`perf_log_file`,
default `logs/perf_run.log`) — never the console. So you run the script exactly
as normal (its usual INFO logs stream to the terminal and the standard timestamped
log file, untouched) and watch perf output by tailing the separate file in another
terminal. When `track_performance = False` it's a true no-op (no thread, no file).

Each input file is bracketed into the three heavy phases:


| Phase                      | What it measures                                                   |
| -------------------------- | ------------------------------------------------------------------ |
| `create_temp_csv`          | ingest input → mapped temp CSV → rows loaded into the parser       |
| `parse_data`               | rows → in-memory object arrays (clients/reports/findings/assets/…) |
| `generate_ptrac_json_data` | object arrays → ptrac JSON per report                              |


Each phase tracks wall time, process **RSS** (start / peak / end / delta), the
relevant object counts, and throughput. Sample of `logs/perf_run.log`:

```
[perf] >> parse_data starting (rss 312.4 MB)
[perf]   .. parse_data: 5.0 s elapsed, rss 1.8 GB (peak 1.8 GB)
[perf] << parse_data done in 11.30 s  peak rss 2.9 GB  dRSS 2.6 GB  | input_rows=1,000,000 findings=250,000 assets=100,000
... (report table with per-phase time %, RSS, throughput, and a TOTAL line) ...
```

How it stays cheap (since runtime is itself a metric): RSS is sampled on a
background thread, so the row loops are never instrumented; the file is written
only at phase boundaries plus a 5 s heartbeat — never per row. `tracemalloc` is
deliberately avoided because its per-allocation overhead would inflate the timing.

The perf file is opened in **append** mode, so successive runs (and multiple input
files in one run) accumulate behind a timestamped `===== <file> @ <time> =====`
banner. Clear it between sessions with `: > logs/perf_run.log` if you want.

### Watching it live (two terminals)

```bash
# Terminal 1 — start once and leave running. `tail -F` follows by name and
# tolerates the file not existing yet, so you don't need to pre-create it:
tail -F logs/perf_run.log
# Powershell
Get-Content -Path perf_run.log -Wait

# Terminal 2 — run the import exactly as normal. INFO logs show here as usual;
# the [perf] lines do NOT — they land in logs/perf_run.log (Terminal 1).
python main.py
```

> If your `tail` has no `-F` (older builds), create the file first so plain
> `tail -f` has something to open: `: > logs/perf_run.log` then `tail -f logs/perf_run.log`.

> The heartbeat's live RSS line is the quickest way to watch *where* in a phase
> memory blows up on the big files (e.g. RSS climbing steadily through
> `generate_ptrac_json_data` on an interleaved run).

### Measuring the cost of per-row logging (phase 1)

`parse_data` emits a handful of `log.info` lines **per row**. At millions of rows
that is a real chunk of phase-1 runtime. Because perf output is in its own file,
measuring this is just running the same input twice with the console logging
toggled and comparing the `parse_data` time in `logs/perf_run.log`:


| Run         | settings.py                                                        | parse_data time |
| ----------- | ------------------------------------------------------------------ | --------------- |
| logging ON  | `console_log_level = logging.INFO`, `save_logs_to_file = False`    | `T_with`        |
| logging OFF | `console_log_level = logging.WARNING`, `save_logs_to_file = False` | `T_without`     |


Per-row logging cost ≈ `**T_with − T_without*`*. (`save_logs_to_file = False` keeps
the file handler from adding a second sink that would muddy the comparison; flip
it on separately if you want to measure the file-logging cost too.)

> Caveat: the `log.info(...)` calls (and the f-string they build) still execute
> in the OFF run — they're just discarded below the WARNING threshold. So the
> delta measures the cost of *formatting + writing* the records, not the cost of
> the log calls existing. Removing that residual would mean changing the hot loop
> in `csv_parser.py`, which this test deliberately leaves untouched.

