# Repository Guidance

This project is two things at once:

1. **General CSV Import — the header-mapping flow.** The original purpose, and the
   **only mapping type that is fully built out and usable as-is**. A user maps the
   columns of any data CSV onto PlexTrac fields with a two-row "header mapping" CSV.
   It does not require `--type`: supplying `--headers-file-path` (or
   `headers_file_path` in config) auto-selects the `header_mapping` type.
2. **A template for custom mapping types.** Cloned per customer project. The
   `example_*` mapping types (`example_csv`, `example_json`, `example_dradis_csv`,
   `example_dradis_zip`) are reference implementations, not finished importers —
   they exist to show how to add a new mapping type for a specific source format.

Either way it transforms source data into PlexTrac PTRAC files, with optional
direct import into PlexTrac. See `README.md` for full user-facing detail.

## Project Layout
- `main.py`: CLI orchestration, config/CLI defaulting, input file discovery, PTRAC generation, optional PlexTrac import, and report template/finding layout lookup.
- `mappings.py`: mapping dictionaries, mapping-type registration (`MapType`, `_MapSpec`, `resolve()`), load/verify functions, and source-to-temp-CSV builders.
- `csv_parser.py`: the generic temp-CSV-to-PTRAC engine. Treat it as the core parser "black box" unless a change is clearly required.
- `mapping_utils/`: shared helpers for source parsing and data shaping. Add code here only when it is genuinely reusable across mappings; keep mapping-specific logic in mapping-specific modules.
- `api/`: thin PlexTrac API wrappers. `utils/`: authentication, input, API request handling, data lookup, validation, and file helpers.
- `tests/`: pytest coverage for parser behavior, mappings, and utilities. Do not create or use a root `test/` directory.
- `docs/mapping_definitions/`: one mapping definition document per mapping type (created during the discovery step before implementation).
- `exported_ptracs/` and `failed_ptracs/`: generated output folders, not source fixtures unless the user explicitly says otherwise.
- `config.yaml`: local run configuration. It can contain customer paths and credentials; do not commit it or expose secrets from it unless the user explicitly requests it.

## Development Workflow
- Work on the current branch unless the user explicitly asks for a new branch or worktree. Do not stage or commit files unless explicitly requested.
- Prefer small, targeted changes that preserve the existing CLI and mapping behavior unless the task says otherwise. When adding a mapping type, touch only the files required for that new mapping, its definition doc, and its focused tests.
- Add or update tests in `tests/` for behavior changes and bug fixes.
- Run targeted tests first, then the broader suite when practical: `python -m pytest tests -q`.
- For syntax checks, use `python -m py_compile main.py mappings.py csv_parser.py mapping_utils/*.py utils/input_utils.py`.

## Header Mapping CSV Flow
- A header mapping CSV is a **two-row** file: row 1 is the data file's exact column headers, row 2 is the PlexTrac location key for each column (blank or `no_mapping` to skip). `Location Key List.md` is the source of truth for valid keys.
- It is selected automatically when `--headers-file-path`/`headers_file_path` is set; `run()` falls back to `MapType.HEADER_MAPPING` when no `--type` is given. Do not require users to pass `--type` for this flow.
- Folder-mode caveat: the header mapping CSV must not live in the same folder as the data files, because `--data-folder-path` discovers every `*.csv` as a potential input and would parse the header CSV as data.

## Config / CLI Resolution
- Precedence is CLI > `config.yaml` > built-in default, implemented in `apply_config_defaults()` (`main.py`). `create_argument_parser()` sets every default to `None` so a `None` reliably means "not passed on the CLI"; `parse_args()` then layers config and defaults underneath.
- Config keys are the **underscored** flag names (`data_file_path`, `force_create_clients`, etc.). Only the keys enumerated in `apply_config_defaults()` are honored — arbitrary extra keys in `config.yaml` are loaded but silently ignored. If you add a new flag, add it to both `create_argument_parser()` and the relevant `string_defaults`/`boolean_defaults` map, or config support for it will be missing.
- Only one of `--data-file-path` or `--data-folder-path` should be provided for a run.

## Import Behavior Notes
- `--force-create-clients` is off by default and that is intentional. When off, PTRACs whose client name has no exact match in PlexTrac are skipped, and the missing names are written to `logs/missing_plextrac_clients.txt`. The intended workflow is: run once to generate that file, have a human verify the names are not near-duplicates of existing clients, then re-run with `--force-create-clients`. Do not flip this default.
- `--limit-to-client-name` filters generated PTRACs to an exact client-name match before save/import; it is distinct from `--client-name`, which injects a source client name and does not filter.
- The multipart PTRAC upload must be passed through the request handler's `files=` channel, not `data=` (which JSON-encodes and fails on the `BytesIO` buffer).

## Adding A New Mapping Type
When asked to add a mapping for a new source format, do the discovery and documentation BEFORE writing implementation code.

1. Inspect the provided source files (CSV, JSON, XML/ZIP, API export, or paired files). Identify which source should be treated as the source of truth.
2. Inventory every potential source data point — columns, object/record fields, nested sections, relationships, identifiers, attachments, and any notes/metadata. Map the source object graph onto the PlexTrac model (client -> report -> finding, client assets, affected-asset relational data), not just individual fields.
3. Create a mapping definition document (see the next section) and present it to the user for confirmation before implementing.
4. Implement the mapping in `mappings.py`: add a mapping dictionary, the needed load/verify/temp-CSV builder functions, a `MapType` value, a `_MapSpec` entry (folder-discovery function, rich-text flag, default merge strategy), and a `resolve()` branch.
5. Do mapping, validation, cleanup, fallback selection, enrichment, and source-specific shaping in the temp-CSV builder for that mapping — keep it out of `csv_parser.py`.
6. Add focused tests proving the mapping reads the expected source fields and produces the expected temp-CSV/PTRAC output.

The `example_*` mapping types are the pattern references: `example_csv` (flat CSV-driven), `example_json` (JSON-driven), `example_dradis_csv` (CSV-driven with a paired ZIP for enrichment), and `example_dradis_zip` (XML/graph-driven, where the unit of import is one row per finding/asset pairing and the spec uses a `user_defined_fields` merge strategy). Pick the closest pattern as scaffold; build the real mapping as its own independent type.

## Generating A Data Source Mapping Definition Document
When adding a new mapping type, always produce a mapping definition document at `docs/mapping_definitions/<map_type>_mapping_definition.md` and present it to the user for verification BEFORE writing any mapping code. The base template ships no sample, so generate one from the outline below. Keep it concise but complete; the goal is a human-reviewable contract for where each source field lands in PlexTrac.

A mapping definition document should contain, in order:
1. **Title and summary** — the map type name and a one-paragraph description of which source files it reads and which source is the source of truth.
2. **Source data model** — the source object types, records, containers, relationships, identifiers, and any detection or matching rules the mapping depends on.
3. **PlexTrac object model** — the destination shape: `CLIENT -> REPORT -> FINDING`, the single client-asset object, and that an affected asset is a copy of a client asset plus relational fields (location URL, ports).
4. **Structural object-to-object mapping** — how source data maps onto the PlexTrac graph (a short bullet list or small diagram), including what the unit of import is and whether finding rows merge.
5. **Field mapping tables** — one table per destination area (client/report, report narratives, findings, assets + evidence, tags, custom fields). Each row: source path/column, example value, PlexTrac location key, planned field, and notes.
6. **Source inventory tables** — one table per source file/object family. List EVERY discovered source field with an example value, its planned mapping, and a short reason for any field intentionally not mapped (internal IDs, workflow/sync metadata, empty placeholders, or other source-only data).

After generating the document, wait for confirmation or edits before implementing. Only include source features the actual source files contain; do not invent structures.

The PlexTrac object model (step 3) is the same for every mapping. Describe it like this:

```markdown
## 3. How PlexTrac is structured (destination)

PlexTrac organizes data as **Client → Report → Finding**:

- **Client** — the customer. Has a name and custom fields.
- **Report** — belongs to a client. Has narratives, tags, and custom fields.
- **Finding** — belongs to a report. There is a single kind of finding object; variations are expressed as tags and custom fields on an ordinary finding, not as separate object types.
- **Client asset** — a single asset object (name plus optional custom fields such as environment). Assets belong to the client/report.
- **Affected asset** — there is no separate "affected asset" object. When a finding affects an asset, PlexTrac stores a **copy of the client asset on the finding**, plus relational detail: a location URL and one or more ports (number + protocol). A finding can affect many assets.
```

## Mapping Boundaries
- Mapping, validation, source cleanup, fallback selection, enrichment, field normalization, and source-specific shaping belong in the temp-CSV builder for the mapping.
- `csv_parser.py` should remain a generic temp-CSV-to-PTRAC builder. Only change it when the PTRAC output model itself needs new generic behavior that cannot reasonably live in a mapping or helper.
- Shared helpers in `mapping_utils/` are for behavior that is genuinely reused across mappings. If helper logic becomes specific to one mapping, put it in a mapping-specific helper module rather than making shared utilities brittle.
- Existing completed mappings must not change behavior when adding a new one. If a shared helper must change, verify existing mappings still behave identically, or add a new helper instead.

## Suggested Prompt For New Mappings
If the user gives a short prompt such as "add a mapping for these files", expand it into this working plan before coding:

```text
Add a new mapping type named "<map_type>" using the source file(s) at "<path>".

First inspect the existing example mapping patterns and pick the closest one as a scaffold reference (CSV-driven, JSON-driven, or XML/graph-driven).

Before implementation, create `docs/mapping_definitions/<map_type>_mapping_definition.md`. Inventory all potential source data points from the source file(s), then create mapping tables for client, report, report narratives, findings, assets, evidence, tags, and custom fields. Include all discovered source fields in the source inventory. Only map fields that make sense in PlexTrac; explicitly mark internal IDs, workflow history, sync metadata, empty placeholders, and source-only fields as not mapped with reasons.

After the mapping definition is written and confirmed, implement the full mapping. Only touch files required for this new mapping type and its tests. Do not change existing mapping behavior. Add helper logic to shared utilities only when it is genuinely reusable; otherwise keep it mapping-specific. Avoid changing `csv_parser.py` unless a generic PTRAC-generation capability is truly required.

Work on the current branch. Do not stage or commit files. I will review and commit after verification.
```

Use that expanded intent when creating new mapping types even when the user prompt is less detailed, unless it conflicts with an explicit instruction from the user.

## Rich Text
- Rich-text conversion (Textile-to-HTML, embedded image extraction) is opt-in per mapping spec. The implementation is Dradis-specific: Textile is the rich-text format Dradis uses in issue/evidence/content-block fields, and image extraction relies on the Dradis ZIP folder structure (attachment files stored inside the same ZIP as `dradis-repository.xml`). Do not enable `enable_rich_text_processing` on non-Dradis mappings; the Textile parser and image resolver will not behave correctly for other data sources.
