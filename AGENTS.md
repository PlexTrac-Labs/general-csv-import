# Repository Guidance

This is the template import project that is cloned for each customer project. It
transforms source data (CSV, JSON, header-mapped CSV, or Dradis CSV+ZIP exports)
into PlexTrac PTRAC files, with optional direct import into PlexTrac.

## Project Layout
- Runtime code lives at the repository root and in `api/`, `utils/`, and `mapping_utils/`.
- Tests live in `tests/`. Do not create or use a root `test/` directory.
- Generated outputs live in `exported_ptracs/` and `failed_ptracs/`. They are not source fixtures unless explicitly requested.
- `config.yaml` can contain local credentials and customer file paths. Do not commit it unless the user explicitly requests it.

## Development Workflow
- Prefer small, targeted changes that preserve the existing CLI and mapping behavior unless the task says otherwise.
- Add or update tests in `tests/` for behavior changes and bug fixes.
- Run targeted tests first, then the broader suite when practical: `python -m pytest tests -q`.
- For syntax checks, use `python -m py_compile main.py mappings.py csv_parser.py utils/input_utils.py`.

## Mapping Guidance
- New Dradis mappings should be independent `dradis_*` mapping types, each with its own mapping dictionary and temp-CSV builder. Use `dradis_example` as the scaffold reference.
- Shared helpers belong in `mapping_utils/dradis_utils.py` only when they are truly reusable. Customer-specific field choices belong in mapping-specific code and docs.
- `csv_parser.py` should remain a generic temp-CSV-to-PTRAC builder. Only change it when the PTRAC output model itself needs new generic behavior.

## Compatibility Notes
- The header mapping workflow uses `data_file_path`/`data_folder_path` and `headers_file_path` from `config.yaml` or CLI overrides.
- CLI values should override `config.yaml` values.
- Only one of `--data-file-path` or `--data-folder-path` should be provided for a run.
- Rich-text conversion (Textile-to-HTML, embedded image extraction) is opt-in and only runs for `dradis_*` mapping types.
