"""Opt-in runtime performance / memory tracking for the import pipeline.

Enabled via ``settings.track_performance``. This is deliberately a settings flag
rather than a CLI argument so it stays out of the user-facing docs - it's a
developer/perf-testing tool, not a product feature.

All output goes to a DEDICATED file (``settings.perf_log_file``, e.g.
``logs/perf_run.log``) - never the console. So the normal run prints its usual
INFO logs to the terminal untouched, and you watch perf output by tailing that
separate file in another terminal.

When disabled, every entry point is a cheap no-op (no threads, no timing, no
file) so normal runs are completely unaffected. When enabled, it brackets the
three heavy pipeline phases and records, per phase:

    * wall time (time.perf_counter)
    * process RSS at start / peak / end, and the net delta
    * caller-supplied object counts (e.g. findings/assets in memory, ptracs out)
    * derived throughput (objects or rows per second)

Design notes
------------
* Memory is the headline metric, so we read true process RSS (resident set),
  not Python-tracked allocations. ``tracemalloc`` is intentionally NOT used: it
  adds per-allocation overhead that would inflate the wall-time we're measuring.
* RSS is sampled on a background daemon thread at a fixed interval, so per-phase
  PEAK memory is captured without adding any instrumentation to the row loops.
  Sampling 10x/sec costs well under 0.1% and never touches the hot path.
* All file output happens at phase boundaries plus an optional periodic
  heartbeat - never per row - so the writing itself doesn't distort timing.

Usage (see main.process_input_file):

    tracker = perf_tracker.PerfTracker(enabled=settings.track_performance,
                                       label=os.path.basename(path),
                                       log_path=settings.perf_log_file)
    with tracker.phase("parse_data") as ph:
        parser.parse_data()
        ph.set_counts(findings=len(parser.findings), assets=len(parser.assets))
    tracker.report()
"""

import os
import sys
import threading
import time
from contextlib import contextmanager

import paths


# --------------------------------------------------------------------------- #
# Low-overhead, dependency-free RSS reader (resolved once at import).
# --------------------------------------------------------------------------- #
def _make_rss_reader():
    """Return a zero-arg callable -> current process RSS in bytes (or None)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            from ctypes import wintypes

            class _PMC(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            psapi = ctypes.WinDLL("psapi.dll")
            kernel32 = ctypes.WinDLL("kernel32.dll")
            get_current_process = kernel32.GetCurrentProcess
            get_current_process.restype = wintypes.HANDLE
            get_mem_info = psapi.GetProcessMemoryInfo
            get_mem_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]

            def _rss_win():
                counters = _PMC()
                counters.cb = ctypes.sizeof(_PMC)
                if get_mem_info(get_current_process(), ctypes.byref(counters), counters.cb):
                    return counters.WorkingSetSize
                return None

            # validate once
            if _rss_win() is not None:
                return _rss_win
        except Exception:
            pass

    # Linux: /proc/self/statm -> (size, resident, ...) in pages
    if os.path.exists("/proc/self/statm"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")

            def _rss_proc():
                try:
                    with open("/proc/self/statm", "r") as fh:
                        return int(fh.read().split()[1]) * page_size
                except Exception:
                    return None

            if _rss_proc() is not None:
                return _rss_proc
        except Exception:
            pass

    # POSIX fallback: resource.ru_maxrss (peak only - better than nothing)
    try:
        import resource

        def _rss_resource():
            maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return maxrss if sys.platform == "darwin" else maxrss * 1024  # macOS=bytes, Linux=KiB

        return _rss_resource
    except Exception:
        return lambda: None


_read_rss = _make_rss_reader()


# --------------------------------------------------------------------------- #
# Formatting helpers
# --------------------------------------------------------------------------- #
def _fmt_bytes(n):
    if n is None:
        return "n/a"
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{sign}{int(n)} B" if unit == "B" else f"{sign}{n:.1f} {unit}"
        n /= 1024


def _fmt_secs(s):
    if s < 1:
        return f"{s * 1000:.0f} ms"
    if s < 60:
        return f"{s:.2f} s"
    return f"{int(s // 60)}m {s % 60:04.1f}s"


# --------------------------------------------------------------------------- #
# Records + handles
# --------------------------------------------------------------------------- #
class _PhaseRecord:
    __slots__ = ("name", "wall", "rss_start", "rss_end", "rss_peak", "counts")

    def __init__(self, name):
        self.name = name
        self.wall = 0.0
        self.rss_start = None
        self.rss_end = None
        self.rss_peak = None
        self.counts = {}


class _ActivePhase:
    """Yielded into the with-block; lets the caller attach object counts."""

    __slots__ = ("_record",)

    def __init__(self, record):
        self._record = record

    def set_counts(self, **counts):
        for key, value in counts.items():
            if value is not None:
                self._record.counts[key] = value


class _NullPhase:
    """No-op handle used when tracking is disabled."""

    __slots__ = ()

    def set_counts(self, **counts):
        pass


_NULL_PHASE = _NullPhase()

# Count keys (in priority order) used to derive a phase's throughput line.
_THROUGHPUT_KEYS = ("input_rows", "rows", "findings", "ptracs")


class PerfTracker:
    def __init__(self, enabled=False, label="", log_path=None,
                 sample_interval=0.1, heartbeat=5.0):
        """
        :param enabled: master switch; when False all methods are no-ops
        :param label: shown in the report header (typically the input filename)
        :param log_path: dedicated file for ALL perf output (never the console)
        :param sample_interval: seconds between background RSS samples
        :param heartbeat: seconds between live "… still running" lines (0 disables)
        """
        self.enabled = bool(enabled)
        self.label = label
        self.log_path = log_path if log_path is not None else str(paths.LOGS_DIR / "perf_run.log")
        self.sample_interval = sample_interval
        self.heartbeat = heartbeat
        self.records = []
        self._fh = None

    def _emit(self, msg):
        """Write one line to the dedicated perf file (never stdout/stderr)."""
        if not self.enabled:
            return
        if self._fh is None:
            try:
                parent = os.path.dirname(self.log_path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                # Append (so multiple files in a run and successive runs accumulate)
                # with line buffering + explicit flush so `tail -F` shows it live.
                self._fh = open(self.log_path, "a", encoding="utf-8", buffering=1)
                self._fh.write(f"\n[perf] ===== {self.label or 'run'} @ "
                               f"{time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            except Exception:
                # never let perf instrumentation break an import
                self.enabled = False
                return
        try:
            self._fh.write(msg + "\n")
            self._fh.flush()
        except Exception:
            pass

    def _close(self):
        if self._fh is not None:
            try:
                self._fh.flush()
                self._fh.close()
            finally:
                self._fh = None

    @contextmanager
    def phase(self, name):
        if not self.enabled:
            yield _NULL_PHASE
            return

        record = _PhaseRecord(name)
        record.rss_start = _read_rss()
        record.rss_peak = record.rss_start or 0
        stop = threading.Event()
        t0 = time.perf_counter()

        def _sampler():
            peak = record.rss_peak
            last_beat = t0
            while not stop.wait(self.sample_interval):
                cur = _read_rss()
                if cur is not None and cur > peak:
                    peak = cur
                if self.heartbeat:
                    now = time.perf_counter()
                    if now - last_beat >= self.heartbeat:
                        last_beat = now
                        self._emit(f"[perf]   .. {name}: {_fmt_secs(now - t0)} elapsed, "
                                   f"rss {_fmt_bytes(cur)} (peak {_fmt_bytes(peak)})")
            record.rss_peak = peak

        sampler = threading.Thread(target=_sampler, name=f"perf-{name}", daemon=True)
        self._emit(f"[perf] >> {name} starting (rss {_fmt_bytes(record.rss_start)})")
        sampler.start()
        active = _ActivePhase(record)
        try:
            yield active
        finally:
            record.wall = time.perf_counter() - t0
            stop.set()
            sampler.join(timeout=1.0)
            record.rss_end = _read_rss()
            if record.rss_end is not None and record.rss_end > record.rss_peak:
                record.rss_peak = record.rss_end
            self.records.append(record)
            counts = "  ".join(f"{k}={v:,}" for k, v in record.counts.items())
            self._emit(f"[perf] << {name} done in {_fmt_secs(record.wall)}  "
                       f"peak rss {_fmt_bytes(record.rss_peak)}  "
                       f"dRSS {_fmt_bytes((record.rss_end or 0) - (record.rss_start or 0))}"
                       + (f"  | {counts}" if counts else ""))

    def report(self):
        if not self.enabled or not self.records:
            self._close()
            return
        bar = "=" * 78
        self._emit(bar)
        self._emit("[perf] PERFORMANCE REPORT" + (f" - {self.label}" if self.label else ""))
        self._emit(bar)
        total_time = sum(r.wall for r in self.records)
        for r in self.records:
            pct = (r.wall / total_time * 100) if total_time else 0
            self._emit(f"  {r.name}")
            self._emit(f"    time      : {_fmt_secs(r.wall)}  ({pct:.0f}% of tracked)")
            self._emit(f"    rss       : start {_fmt_bytes(r.rss_start)}  "
                       f"peak {_fmt_bytes(r.rss_peak)}  end {_fmt_bytes(r.rss_end)}  "
                       f"delta {_fmt_bytes((r.rss_end or 0) - (r.rss_start or 0))}")
            if r.counts:
                self._emit("    objects   : " + "  ".join(f"{k}={v:,}" for k, v in r.counts.items()))
                for key in _THROUGHPUT_KEYS:
                    if r.counts.get(key) and r.wall > 0:
                        unit = "rows" if key in ("input_rows", "rows") else key
                        self._emit(f"    throughput: {r.counts[key] / r.wall:,.0f} {unit}/s")
                        break
        self._emit("  " + "-" * 74)
        peak = max((r.rss_peak or 0) for r in self.records)
        net = (self.records[-1].rss_end or 0) - (self.records[0].rss_start or 0)
        self._emit(f"  TOTAL  time {_fmt_secs(total_time)}   peak rss {_fmt_bytes(peak)}   "
                   f"net dRSS {_fmt_bytes(net)}")
        self._emit(bar)
        self._close()
