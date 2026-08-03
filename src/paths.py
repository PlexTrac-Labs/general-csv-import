"""Filesystem anchors for the importer.

All runtime paths (config, logs, exported/failed PTRACs, input data) are resolved
against these constants instead of the current working directory, so the script
behaves the same no matter where it is launched from.

Layout:
    <PROJECT_ROOT>/
        src/          <- SRC_DIR (this package; code + config.yaml)
        data/         <- DATA_DIR (exported_ptracs, failed_ptracs, testing_files, input_files)
        logs/         <- LOGS_DIR
"""

from pathlib import Path

# Directory holding this file (the code package).
SRC_DIR = Path(__file__).resolve().parent

# Repository root, one level above src/.
PROJECT_ROOT = SRC_DIR.parent

# Consolidated I/O root: script inputs and generated outputs.
DATA_DIR = PROJECT_ROOT / "data"

# Log output (kept separate from data/).
LOGS_DIR = PROJECT_ROOT / "logs"

# Default config lives next to the code.
CONFIG_FILE = SRC_DIR / "config.yaml"
