# General CSV Import / Import Template

This project is really two things:

1. **General CSV Import — the header-mapping flow.** The original purpose of this
   project. You take any CSV of finding data, describe how its columns map onto
   PlexTrac fields with a small two-row "header mapping" CSV, and the script turns
   it into PlexTrac PTRAC files. This is the **only mapping type that is fully
   built out and ready to use out of the box**, and it does **not** require a
   `--type` flag. See [Header Mapping CSV Import](#header-mapping-csv-import).

2. **A template for building custom mapping types.** Over time the project grew
   into a template that is cloned per custom customer project. It ships several *example* mapping
   types (`example_csv`, `example_json`, `example_dradis_csv`, `example_dradis_zip`)
   that are **not** finished importers — they exist to show how to build your own
   mapping type for a specific source format. See
   [Adding A Parser Type](#adding-a-parser-type).

Either way the script transforms source data into PlexTrac PTRAC files and can
process a single file or a whole folder, then optionally upload the results.

## Requirements
- Python 3.11
- pip
- pipenv

## Install
```bash
pipenv install
```

## Usage
Header-mapping flow (the default, fully-supported path — no `--type` needed):
```bash
pipenv run python main.py --headers-file-path header_mapping.csv --data-file-path input_files/csv_data.csv --api-version 2.19.0
```

Generate PTRAC files from an example CSV mapping type:
```bash
pipenv run python main.py --type example_csv --data-file-path input_files/csv_data.csv --api-version 2.19.0
```

Process an entire folder of inputs in one run:
```bash
pipenv run python main.py --type example_csv --data-folder-path input_files --api-version 2.19.0
```

Optionally import generated PTRACs into PlexTrac:
```bash
pipenv run python main.py --headers-file-path header_mapping.csv --data-file-path input.csv --api-version 2.19.0 --import-to-plextrac --instance-url https://example.plextrac.com --username user@example.com --password password
```

## Header Mapping CSV Import
This is the original, fully-supported import flow. You do **not** pass `--type`:
providing `--headers-file-path` (or `headers_file_path` in `config.yaml`)
automatically selects the `header_mapping` type.

```bash
pipenv run python main.py --headers-file-path header_mapping.csv --data-file-path data.csv --api-version 2.19.0
```

### Building a header mapping CSV
A header mapping CSV tells the script which PlexTrac field each column of your
data file maps to. It is a **two-row** file:

- **Row 1** — the exact column headers from your data file.
- **Row 2** — the PlexTrac *location key* for each column you want to import.
  Leave a cell blank (or use `no_mapping`) for any column you want to skip.

To create one:

1. Make a copy of the CSV file containing the data you want to import.
2. Add a new row directly under the header row (so the headers stay as row 1 and
   the new row becomes row 2).
3. Open `Location Key List.md` to see every field you can import data into in
   PlexTrac.
4. In row 2, under each column you want to map, add the location key for the
   PlexTrac field it should populate. Use the example data values still visible
   in the rows below to help you decide which key fits each column.
5. Delete every row from row 3 down, so the file keeps **only two rows** (headers
   + keys).
6. Save the file in the script root (or anywhere convenient) and set its relative
   path as `headers_file_path` in `config.yaml`, or pass it with
   `--headers-file-path`.

`Location Key List.md` lists every available mapping key you can put in row 2.

### Folder-mode caveat
Do **not** keep the header mapping CSV in the same folder as your data files when
using folder mode (`--data-folder-path`). Folder mode discovers every `*.csv` in
the folder as a potential input, so the header mapping CSV would itself be read as
a data file. Keep it in the script root or a separate directory.

## File vs Folder Mode
- `--data-file-path`: process a single input file.
- `--data-folder-path`: process every matching file in a folder. Each mapping
  spec declares its own discovery behavior: JSON mappings look for `*.json`,
  `example_dradis_csv` looks for CSV files with a same-basename ZIP pair,
  `example_dradis_zip` looks for ZIP exports containing `dradis-repository.xml`,
  and other mappings (including `header_mapping`) look for `*.csv`.

Only one of `--data-file-path` or `--data-folder-path` should be provided. When
both are set, interactive runs prompt for the mode and non-interactive runs fall
back to file mode.

## Report Template / Finding Layout
Use `--report-template-name` and `--findings-layout-name` to resolve PlexTrac
report template and finding layout names through the API and attach their IDs to
generated PTRACs. If lookup fails, generation stops unless
`--force-generate-ptrac` is set. These options require `--instance-url`,
`--username`, and `--password`.

## CLI Flags
Every flag below can also be set in `config.yaml` using its underscored name
(e.g. `data_file_path`, `force_create_clients`). CLI values win over config,
and config wins over the built-in default.

| Flag | Default | Description |
| --- | --- | --- |
| `--type` | none | Parser mapping type from `mappings.MapType` (`example_csv`, `example_json`, `example_dradis_csv`, `example_dradis_zip`, `header_mapping`). Not required when `--headers-file-path` is set, which auto-selects `header_mapping`. |
| `--data-file-path` | `""` | Path to a single input data file. |
| `--data-folder-path` | `""` | Path to a folder of input data files to process. Only one of `--data-file-path` or `--data-folder-path` should be set. |
| `--headers-file-path` | `""` | Header mapping CSV that selects and configures the `header_mapping` flow. See [Header Mapping CSV Import](#header-mapping-csv-import). |
| `--api-version` | `""` | PlexTrac API version (e.g. `2.19.0`) written into generated PTRAC metadata. Must be `major.minor.patch`. |
| `--client-name` | `""` | Source client-name value to inject when the input data or custom mapping does not provide one. This does **not** filter output. |
| `--limit-to-client-name` | `""` | Only save or import generated PTRACs whose resolved PlexTrac client name exactly matches this value. Distinct from `--client-name`. |
| `--report-name` | `""` | Optional report name override for custom mappings. |
| `--report-template-name` | `""` | PlexTrac report template name to resolve via the API and attach to generated PTRACs. Requires import credentials. |
| `--findings-layout-name` | `""` | PlexTrac finding layout name to resolve via the API and attach to generated PTRACs. Requires import credentials. |
| `--force-generate-ptrac` | `false` | Continue PTRAC generation after recoverable template/layout lookup errors instead of stopping. |
| `--finding-merge-strategy` | `none` | How to merge findings: `none`, `title`, `user_defined_fields`, or `all_fields`. See [Merge Strategies](#merge-strategies). |
| `--output-dir` | `exported_ptracs` | Directory for generated PTRAC files (ignored when `--import-to-plextrac` is set). |
| `--import-to-plextrac` | `false` | Upload generated PTRACs to PlexTrac instead of writing them to `--output-dir`. |
| `--force-create-clients` | `false` | Create missing PlexTrac clients during import instead of skipping their reports. **Off by default** — see [Force Create Clients](#force-create-clients). |
| `--instance-url` | `""` | PlexTrac instance URL (e.g. `https://example.plextrac.com`). Required for `--import-to-plextrac` and template/layout lookup. |
| `-u`, `--username` | `""` | PlexTrac username. Required for import and template/layout lookup. |
| `-p`, `--password` | `""` | PlexTrac password. Required for import and template/layout lookup. |

## Force Create Clients
`--force-create-clients` is **off by default**, and that default is deliberate.

During import the script matches each generated PTRAC's client name against the
clients that already exist in the target PlexTrac instance. By default, any PTRAC
whose client name has no exact match is **skipped** rather than imported, and the
script writes every missing client name to `logs/missing_plextrac_clients.txt`.

The problem this guards against: imagine a user has already started building out
clients in a new PlexTrac instance, and then needs to migrate data from an older
source. If the old source spells client names even slightly differently
("Acme Inc" vs "Acme, Inc."), auto-creating clients on a name miss would silently
produce **duplicate clients** for what is really one customer. That duplication is
tedious to detect and clean up after the fact, so the safe default is to skip and
report instead of create.

### Recommended workflow
1. Run the import **without** `--force-create-clients`. Missing clients are
   skipped and their names are written to `logs/missing_plextrac_clients.txt`.
2. Open that file and verify every name. Confirm each one is genuinely a new
   client and not a near-duplicate of an existing PlexTrac client.
3. Re-run the same import **with** `--force-create-clients`. The remaining
   missing clients are created (using the PTRAC's `client_info`) and their
   reports are imported.

This two-pass approach means clients are only ever auto-created after a human has
confirmed the names are correct.

---

# Template: Building Custom Mapping Types

Everything below is the *template* side of the project. The example mapping types
are not finished importers — they are reference implementations that show how to
add your own mapping type for a specific customer source format.

## Example & Dradis Mappings
Dradis exports can be handled in two generic example patterns:
`example_dradis_csv` is CSV-driven and loads a same-basename ZIP for XML/image
enrichment, while `example_dradis_zip` is graph-driven and reads findings,
assets, affected-asset locations, and ports from `dradis-repository.xml`
without reading a CSV. Build real customer mappings as independent types
modeled on the appropriate example.

When a Dradis example mapping is selected, the parser converts Dradis/Textile
rich text to HTML, resolves embedded Dradis image markers out of the ZIP, and
adds those images to `summary.ReportMedia` in each generated PTRAC.

## Adding A Parser Type
1. Add a mapping dictionary in `mappings.py`.
2. Add a load function for the source file type.
3. Add a verify function for required source data.
4. Add a temp-CSV builder that outputs headers from `parser.get_csv_headers()` and one row per finding.
5. Add a `MapType` value.
6. Add a `_MapSpec` entry with the mapping's folder discovery function, rich-text flag, and any default merge strategy.
7. Update `resolve()` to return the new spec.
8. Add focused tests in `tests/`.

## Parser Layout
- `main.py`: command-line orchestration, input discovery, PTRAC generation, and optional PlexTrac import.
- `mappings.py`: parser type definitions, mapping dictionaries, data loaders, data validation, and temp-CSV builders.
- `csv_parser.py`: generic parser and PTRAC builder.
- `mapping_utils/dradis_utils.py`: shared Dradis CSV/ZIP/XML parsing and rich-text helpers.
- `utils/`: authentication, input, API request, data lookup, validation, and file helpers.

## Merge Strategies
- `none`: keep every parsed finding row as its own finding.
- `title`: merge findings with the same title in the same report.
- `user_defined_fields`: merge findings with the same title and matching scalar fields; concatenate differing rich text fields and dedupe list fields.
- `all_fields`: merge only when scalar and rich text fields match exactly; list fields are still deduped.

Asset merging follows the selected finding merge strategy. Duplicate assets in a report are collapsed to a single ReportAsset, while affected asset fields are merged as safely as possible.

## Naming Notes
- `object`: parser-internal object stored on `self.clients`, `self.reports`, `self.findings`, or `self.assets`.
- `object_info`: PTRAC-ready copy of an object after parser-only fields are removed.
- `original_asset`: first asset seen with a given client/name pair.
- `current_asset`: duplicate-aware asset currently being rendered into PTRAC structures.
- `affected_fields`: fields tied to a finding/asset pair.
- `affected_asset_info`: affected asset object stored under a PTRAC finding.

## Building A New Mapping Type With Agentic AI
Adding a mapping type is well suited to an agentic AI coding assistant. `AGENTS.md`
contains instructions written specifically to help an agent navigate the work:
how to inventory a source format, how to produce a mapping definition document for
your review before any code is written, where mapping logic belongs, and how to
register a new mapping type without disturbing the existing ones.

To use it:

1. Create an `input_files/` folder in the repository root.
2. Add as many representative sample data files as you can for the source format
   you want to map. The more complete and varied the samples, the better chance
   the agent has of correctly inferring the mapping.
3. Point the agent at the work with a prompt like the following (or something
   similar tailored to your source):

   ```text
   Go do full research on adding a new mapping type for XXX. Make sure to inspect
   the example data files in input_files/.
   ```

The agent should then follow the workflow in `AGENTS.md`: research the samples,
draft a mapping definition document for you to confirm, and only then implement
the mapping and its tests.
