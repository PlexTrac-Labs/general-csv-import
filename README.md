# General CSV Import Template

Template project for building customer-specific import scripts that transform source data into PlexTrac PTRAC files.

## Requirements
- Python 3
- pip
- pipenv

## Install
```bash
pipenv install
```

## Usage
Generate PTRAC files from an example CSV:
```bash
pipenv run python main.py --type example_csv --input testing_files/csv_data.csv --api-version 2.19.0
```

Generate PTRAC files from an example JSON file:
```bash
pipenv run python main.py --type example_json --input testing_files/test_data.json --api-version 2.19.0
```

Optionally import generated PTRACs into PlexTrac:
```bash
pipenv run python main.py --type example_csv --input input.csv --api-version 2.19.0 --import-to-plextrac --instance-url https://example.plextrac.com --username user@example.com --password password
```

Direct single-object API creation is no longer the preferred template flow. Generate PTRACs first, then optionally upload those PTRACs.

## Parser Layout
- `main.py`: command-line orchestration only.
- `mappings.py`: parser type definitions, mapping dictionaries, data loaders, data validation, and temp-CSV builders.
- `csv_parser.py`: generic parser and PTRAC builder.
- `utils/`: authentication, input, API request, data lookup, validation, and file helpers.

## Adding A Parser Type
1. Add a mapping dictionary in `mappings.py`.
2. Add a load function for the source file type.
3. Add a verify function for required source data.
4. Add a temp-CSV builder that outputs headers from `parser.get_csv_headers()` and one row per finding.
5. Add a `MapType` value.
6. Add a `_MapSpec` entry.
7. Update `resolve()` to return the new spec.

## Important Flags
- `--type`: parser mapping type from `mappings.MapType`.
- `--input`: source data file path.
- `--api-version`: PlexTrac API version used in generated PTRAC metadata.
- `--finding-merge-strategy`: `none`, `title`, `user_defined_fields`, or `all_fields`.
- `--output-dir`: generated PTRAC output directory.
- `--import-to-plextrac`: upload generated PTRACs to PlexTrac.
- `--instance-url`, `--username`, `--password`: required for `--import-to-plextrac`.

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
