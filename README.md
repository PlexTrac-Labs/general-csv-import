# General CSV Import

A PlexTrac utility that turns arbitrary CSV finding data into PlexTrac PTRAC
files (with optional direct import). The importer code lives in [`src/`](src/) —
**see [`src/README.md`](src/README.md) for full usage, flags, and mapping docs.**

## Quick start
Run everything from this directory (the repository root):

```bash
pipenv install
pipenv run python src/main.py --headers-file-path header_mapping.csv --data-file-path data/input_files/csv_data.csv --api-version 2.19.0
```

## Repository layout
```
.
├── src/            # importer code + config.yaml (see src/README.md)
│   ├── main.py         # entry point — run as `python src/main.py`
│   ├── csv_parser.py, mappings.py, settings.py
│   ├── api/  utils/  mapping_utils/
│   ├── paths.py        # anchors all runtime paths to the repo root
│   └── config.yaml
├── data/           # all script I/O (gitignored)
│   ├── input_files/    # put your input data files here
│   ├── exported_ptracs/
│   ├── failed_ptracs/
│   └── testing_files/  # sample + perf data
├── tests/          # pytest suite (run `pipenv run pytest` from root)
├── scripts/        # dev/perf tooling
├── logs/           # run + perf logs (gitignored)
├── docs/
├── AGENTS.md       # guide for adding a new mapping type
└── Pipfile
```

## Running tests
```bash
pipenv run pytest
```
`pytest.ini` puts `src/` on the path, so tests in `tests/` import the modules
directly (`import main`, `from csv_parser import CSVParser`, ...).

## Notes
- Always launch from the repository root; the script is invoked as `src/main.py`.
- Runtime paths are anchored to the repo root via [`src/paths.py`](src/paths.py),
  so outputs land in `data/` and `logs/` no matter the current working directory.
