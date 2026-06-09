# General CSV Import Template

Template project for building customer-specific import scripts that transform
source data into PlexTrac PTRAC files. It is cloned for each specific customer
project. It supports plain CSV, JSON, customer header-mapped CSV, and Dradis
CSV+ZIP or ZIP/XML exports, and can process either a single file or a whole folder.

## Requirements
- Python 3.11
- pip
- pipenv

## Install
```bash
pipenv install
```

## Usage
Generate PTRAC files from an example CSV:
```bash
pipenv run python main.py --type example_csv --data-file-path testing_files/csv_data.csv --api-version 2.19.0
```

Generate PTRAC files from an example JSON file:
```bash
pipenv run python main.py --type example_json --data-file-path testing_files/test_data.json --api-version 2.19.0
```

Process an entire folder of inputs in one run:
```bash
pipenv run python main.py --type example_csv --data-folder-path testing_files/csvs --api-version 2.19.0
```

Generate PTRAC files from a Dradis CSV export (a same-basename `.zip` must sit beside the CSV):
```bash
pipenv run python main.py --type example_dradis_csv --data-file-path "input_files/Project5651.csv" --api-version 2.19.0
```

Generate PTRAC files from a Dradis ZIP/XML export without reading a CSV:
```bash
pipenv run python main.py --type example_dradis_zip --data-file-path "input_files/Project5651.zip" --api-version 2.19.0
```

Optionally import generated PTRACs into PlexTrac:
```bash
pipenv run python main.py --type example_csv --data-file-path input.csv --api-version 2.19.0 --import-to-plextrac --instance-url https://example.plextrac.com --username user@example.com --password password
```

Direct single-object API creation is no longer the preferred template flow.
Generate PTRACs first, then optionally upload those PTRACs.

## Input Modes
- `--data-file-path`: process a single input file.
- `--data-folder-path`: process every matching file in a folder. Each mapping
  spec declares its own discovery behavior: JSON mappings look for `*.json`,
  `example_dradis_csv` looks for CSV files with a same-basename ZIP pair,
  `example_dradis_zip` looks for ZIP exports containing `dradis-repository.xml`,
  and other mappings look for `*.csv`.

Only one of `--data-file-path` or `--data-folder-path` should be provided. When
both are set, interactive runs prompt for the mode and non-interactive runs fall
back to file mode.

## Dradis Mappings
Dradis exports can be handled in two generic example patterns:
`example_dradis_csv` is CSV-driven and loads a same-basename ZIP for XML/image
enrichment, while `example_dradis_zip` is graph-driven and reads findings,
assets, affected-asset locations, and ports from `dradis-repository.xml`
without reading a CSV. Build real customer mappings as independent types
modeled on the appropriate example.

When a Dradis example mapping is selected, the parser converts Dradis/Textile
rich text to HTML, resolves embedded Dradis image markers out of the ZIP, and
adds those images to `summary.ReportMedia` in each generated PTRAC.

## Report Template / Finding Layout
Use `--report-template-name` and `--findings-layout-name` to resolve PlexTrac
report template and finding layout names through the API and attach their IDs to
generated PTRACs. If lookup fails, generation stops unless
`--force-generate-ptrac` is set. These options require `--instance-url`,
`--username`, and `--password`.

## Parser Layout
- `main.py`: command-line orchestration, input discovery, PTRAC generation, and optional PlexTrac import.
- `mappings.py`: parser type definitions, mapping dictionaries, data loaders, data validation, and temp-CSV builders.
- `csv_parser.py`: generic parser and PTRAC builder.
- `mapping_utils/dradis_utils.py`: shared Dradis CSV/ZIP/XML parsing and rich-text helpers.
- `utils/`: authentication, input, API request, data lookup, validation, and file helpers.

## Adding A Parser Type
1. Add a mapping dictionary in `mappings.py`.
2. Add a load function for the source file type.
3. Add a verify function for required source data.
4. Add a temp-CSV builder that outputs headers from `parser.get_csv_headers()` and one row per finding.
5. Add a `MapType` value.
6. Add a `_MapSpec` entry with the mapping's folder discovery function, rich-text flag, and any default merge strategy.
7. Update `resolve()` to return the new spec.
8. Add focused tests in `tests/`.

## Important Flags
- `--type`: parser mapping type from `mappings.MapType` (`example_csv`, `example_json`, `example_dradis_csv`, `example_dradis_zip`, `header_mapping`).
- `--data-file-path` / `--data-folder-path`: single file or folder of inputs.
- `--headers-file-path`: customer header mapping CSV for the `header_mapping` type.
- `--api-version`: PlexTrac API version used in generated PTRAC metadata.
- `--finding-merge-strategy`: `none`, `title`, `user_defined_fields`, or `all_fields`.
- `--output-dir`: generated PTRAC output directory.
- `--report-template-name` / `--findings-layout-name`: PlexTrac template/layout names to attach.
- `--force-generate-ptrac`: continue after recoverable template/layout lookup errors.
- `--import-to-plextrac`: upload generated PTRACs to PlexTrac.
- `--instance-url`, `--username`, `--password`: required for `--import-to-plextrac` and template/layout lookup.

## Merge Strategies
- `none`: keep every parsed finding row as its own finding.
- `title`: merge findings with the same title in the same report.
- `user_defined_fields`: merge findings with the same title and matching scalar fields; concatenate differing rich text fields and dedupe list fields.
- `all_fields`: merge only when scalar and rich text fields match exactly; list fields are still deduped.

Asset merging follows the selected finding merge strategy. Duplicate assets in a report are collapsed to a single ReportAsset, while affected asset fields are merged as safely as possible.

## Evidence Mapping
Use `affected_asset_evidence` to map a source column into affected-asset evidence. The column header becomes the evidence caption and the cell value becomes the code sample.

## Location Keys
See `Location Key List.md` for available mapping keys, including finding merge metadata and affected-asset evidence.

## Naming Notes
- `object`: parser-internal object stored on `self.clients`, `self.reports`, `self.findings`, or `self.assets`.
- `object_info`: PTRAC-ready copy of an object after parser-only fields are removed.
- `original_asset`: first asset seen with a given client/name pair.
- `current_asset`: duplicate-aware asset currently being rendered into PTRAC structures.
- `affected_fields`: fields tied to a finding/asset pair.
- `affected_asset_info`: affected asset object stored under a PTRAC finding.
