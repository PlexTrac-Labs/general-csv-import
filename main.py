from typing import List, Optional
import argparse
import csv
import io
import json
import os
import yaml

import utils.log_handler as logger
log = logger.log
import settings
from csv_parser import CSVParser
from utils.auth_handler import Auth
import utils.input_utils as input
import utils.general_utils as utils
import utils.data_utils as data
import api
import mappings

MISSING_CLIENTS_FILE_NAME = os.path.join("logs", "missing_plextrac_clients.txt")


def load_config_defaults(config_path: str = "config.yaml") -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    return config if isinstance(config, dict) else {}


def handle_load_api_version(api_version: str, parser: CSVParser) -> None:
    """
    Set the PlexTrac API version used in generated PTRAC finding metadata.
    """
    if api_version == "":
        log.critical("No API version provided.")
        exit(1)
    if len(api_version.split(".")) == 3:
        parser.doc_version = api_version
        return

    log.critical(f'Invalid API version format: {api_version}. Expected format is "major.minor.patch".')
    exit(1)


def load_parser_mappings_from_data_file(csv_rows: List[list], parser: CSVParser) -> bool:
    """
    Match generated temp-CSV headers to the injected parser header mapping.
    """
    headers = csv_rows[0]

    for index, header in enumerate(headers):
        mapping_key = parser.get_mapping_key_from_header(header)
        if mapping_key in parser.get_data_mapping_ids():
            if parser.csv_headers_mapping[header].get("matched") is None:
                parser.csv_headers_mapping[header]["col_index"] = index
                parser.csv_headers_mapping[header]["matched"] = True
        else:
            log.error(f"Invalid mapping key '{mapping_key}' for header '{header}'. Marking as 'no_mapping'")
            parser.csv_headers_mapping[header]["mapping_key"] = "no_mapping"

    log.success("Loaded column headings from temp CSV")
    return True


def load_data_into_parser(csv_rows: List[list], parser: CSVParser) -> None:
    """
    Load CSV-like data rows into the parser, excluding the header row.
    """
    parser.csv_data = csv_rows[1:]
    log.success("Loaded data into parser instance")


def save_temp_csv_for_debug(rows: List[list], file_path: str) -> None:
    """Write temp CSV rows (header + data) as UTF-8 for debugging."""
    with open(file_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(rows)
    log.info(f"Saved temp CSV for debug to '{file_path}'")


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser with all defaults set to None.

    Config-file values and hard defaults are layered in separately by
    apply_config_defaults() so a None value reliably means "not provided on the
    CLI" and config can be merged underneath it.
    """
    parser = argparse.ArgumentParser(description="General CSV Import template parser")
    parser.add_argument("--data-file-path", default=None, help="Path to a single input data file.")
    parser.add_argument("--data-folder-path", default=None, help="Path to a folder of input data files to process. Only one of --data-file-path or --data-folder-path should be used.")
    parser.add_argument("--headers-file-path", default=None, help="Path to customer header mapping CSV file.")
    parser.add_argument(
        "--type",
        choices=[map_type.value for map_type in mappings.MapType],
        default=None,
        help="Parser mapping type to use.",
    )
    parser.add_argument("--api-version", default=None, help="PlexTrac API version, e.g. '2.19.0'.")
    parser.add_argument("--client-name", default=None, help="Optional source client-name value to inject when the input data or custom mapping does not provide one. This does not filter output.")
    parser.add_argument("--limit-to-client-name", default=None, help="Only save or import generated PTRACs whose generated PlexTrac client name exactly matches this value. This is distinct from --client-name.")
    parser.add_argument("--report-name", default=None, help="Optional report name override for custom mappings.")
    parser.add_argument("--report-template-name", default=None, help="Optional PlexTrac report template name to attach to generated PTRAC reports.")
    parser.add_argument("--findings-layout-name", default=None, help="Optional PlexTrac finding layout name to attach to generated PTRAC reports.")
    parser.add_argument("--force-generate-ptrac", action="store_true", default=None, help="Continue PTRAC generation after recoverable template/layout lookup errors.")
    parser.add_argument(
        "--finding-merge-strategy",
        choices=["none", "title", "user_defined_fields", "all_fields"],
        default=None,
        help="Optional finding merge strategy.",
    )
    parser.add_argument("--output-dir", default=None, help="Directory for generated PTRAC files.")
    parser.add_argument("--import-to-plextrac", action="store_true", default=None, help="Import generated PTRAC reports into PlexTrac.")
    parser.add_argument("--force-create-clients", action="store_true", default=None, help="Create missing PlexTrac clients during PTRAC import instead of skipping those reports.")
    parser.add_argument("--instance-url", default=None, help="PlexTrac instance URL for import/template lookup.")
    parser.add_argument("-u", "--username", default=None, help="PlexTrac username for import/template lookup.")
    parser.add_argument("-p", "--password", default=None, help="PlexTrac password for import/template lookup.")
    return parser


def apply_config_defaults(args: argparse.Namespace, config: Optional[dict] = None) -> argparse.Namespace:
    """
    Layer config-file values and hard defaults underneath the parsed CLI args.

    Only fields still set to None (i.e. not provided on the CLI) are filled, so
    CLI values always win over config, which in turn wins over the hard default.
    """
    if config is None:
        config = load_config_defaults()

    string_defaults = {
        "data_file_path": "",
        "data_folder_path": "",
        "headers_file_path": "",
        "type": None,
        "api_version": "",
        "client_name": "",
        "limit_to_client_name": "",
        "report_name": "",
        "report_template_name": "",
        "findings_layout_name": "",
        "finding_merge_strategy": "none",
        "output_dir": "exported_ptracs",
        "instance_url": "",
        "username": "",
        "password": "",
    }
    boolean_defaults = {
        "force_generate_ptrac": False,
        "import_to_plextrac": False,
        "force_create_clients": False,
    }

    for field_name, default_value in string_defaults.items():
        if getattr(args, field_name) is None:
            config_value = config.get(field_name, default_value)
            setattr(args, field_name, default_value if config_value is None else config_value)

    for field_name, default_value in boolean_defaults.items():
        if getattr(args, field_name) is None:
            setattr(args, field_name, bool(config.get(field_name, default_value)))

    return args


def parse_args(cli_args=None) -> argparse.Namespace:
    """
    Parse CLI args and merge config-file defaults underneath them.
    """
    config = load_config_defaults()
    parser = create_argument_parser()
    args = parser.parse_args(cli_args)
    return apply_config_defaults(args, config)


def filter_ptracs_by_client_name(ptracs: list, client_name_filter: str) -> list:
    """
    Keep only generated PTRACs whose PlexTrac client name exactly matches the requested filter.
    """
    if not client_name_filter:
        return ptracs

    filtered_ptracs = [
        ptrac for ptrac in ptracs
        if ptrac.get("client_info", {}).get("name", "") == client_name_filter
    ]
    skipped_count = len(ptracs) - len(filtered_ptracs)
    log.info(f"Client-name filter '{client_name_filter}' kept {len(filtered_ptracs)} PTRAC(s) and skipped {skipped_count}.")
    return filtered_ptracs


def write_missing_clients_file(client_names: list, file_path: str = MISSING_CLIENTS_FILE_NAME) -> None:
    """
    Write a sorted unique list of PlexTrac client names that were missing during import.
    """
    missing_client_names = sorted({client_name for client_name in client_names if client_name})
    if not missing_client_names:
        return None

    directory = os.path.dirname(file_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as file:
        for client_name in missing_client_names:
            file.write(f"{client_name}\n")

    log.warning(f"Wrote {len(missing_client_names)} missing PlexTrac client name(s) to '{file_path}'.")
    return None


def deepcopy_client_info(ptrac: dict) -> dict:
    """
    Return a JSON-safe copy of a PTRAC's client_info, stripped of tenant-scoped fields.
    """
    client_info = json.loads(json.dumps(ptrac.get("client_info", {}), default=str))
    client_info.pop("tenant_id", None)
    client_info.pop("doc_type", None)
    return client_info


def create_plextrac_client_from_ptrac(ptrac: dict, auth: Auth) -> Optional[dict]:
    """
    Create the PlexTrac client described by a PTRAC and return a local client-list item.
    """
    client_info = deepcopy_client_info(ptrac)
    client_name = client_info.get("name", "")
    if not client_name:
        return None

    response = api.clients.create_client(auth.base_url, auth.get_auth_headers(), client_info)
    response_json = getattr(response, "json", {}) or {}
    if response_json.get("status") not in [None, "success"]:
        raise RuntimeError(f"Create client response was not successful: {response_json}")

    client_id = response_json.get("client_id") or response_json.get("id")
    if not client_id:
        data_item = response_json.get("data") if isinstance(response_json.get("data"), dict) else {}
        client_id = data_item.get("client_id") or data_item.get("id")
    if not client_id:
        raise RuntimeError(f"Create client response did not include a client_id: {response_json}")

    return {"client_id": client_id, "name": client_name}


def import_ptracs_to_plextrac(ptracs: list, args: argparse.Namespace) -> None:
    auth = Auth(args)
    auth.handle_authentication()
    force_create_clients = getattr(args, "force_create_clients", False)

    clients = []
    if not data.get_page_of_clients(clients=clients, auth=auth):
        log.critical("Could not load clients from PlexTrac. Exiting...")
        exit(1)
    if len(clients) < 1 and not force_create_clients:
        log.critical("Did not find any clients in PlexTrac instance. Exiting...")
        exit(1)

    reports = []
    if not data.get_page_of_reports(reports=reports, auth=auth):
        log.critical("Could not load reports from PlexTrac. Exiting...")
        exit(1)

    report_names_by_client_id = {}
    for report in reports:
        report_names_by_client_id.setdefault(report["client_id"], []).append(report["name"])

    failed_reports = []
    missing_client_names = []
    for ptrac in ptracs:
        client_name = ptrac.get("client_info", {}).get("name", "")
        report_name = ptrac.get("report_info", {}).get("name", "")
        if not client_name or not report_name:
            log.error("Generated PTRAC is missing client or report name. Skipping...")
            failed_reports.append(f"Client: {client_name} | Report: {report_name}")
            utils.save_json_as_ptrac_file(ptrac, folder_path="failed_ptracs")
            continue

        matching_clients = [client for client in clients if client_name == client["name"]]
        if len(matching_clients) == 0:
            if not force_create_clients:
                log.error(f"Mapped client name '{client_name}' does not exist in PlexTrac. Skipping...")
                failed_reports.append(f"Client: {client_name} | Report: {report_name}")
                missing_client_names.append(client_name)
                utils.save_json_as_ptrac_file(ptrac, folder_path="failed_ptracs")
                continue

            try:
                created_client = create_plextrac_client_from_ptrac(ptrac, auth)
                if created_client is None:
                    raise RuntimeError("PTRAC did not include a client name.")
                clients.append(created_client)
                matching_clients = [created_client]
                log.success(f"Created missing PlexTrac client '{client_name}'")
            except Exception as e:
                log.error(f"Could not create missing PlexTrac client '{client_name}'. Skipping report '{report_name}'...\n{e}")
                failed_reports.append(f"Client: {client_name} | Report: {report_name}")
                missing_client_names.append(client_name)
                utils.save_json_as_ptrac_file(ptrac, folder_path="failed_ptracs")
                continue

        client_id = matching_clients[0]["client_id"]
        if report_name in report_names_by_client_id.get(client_id, []):
            log.warning(f"Report '{report_name}' already exists under client '{client_name}'. Skipping...")
            failed_reports.append(f"Client: {client_name} | Report: {report_name}")
            utils.save_json_as_ptrac_file(ptrac, folder_path="failed_ptracs")
            continue

        try:
            file_name = f"{report_name}.json"
            file_buf = io.BytesIO(json.dumps(ptrac, ensure_ascii=False).encode("utf-8"))
            file_buf.seek(0)
            multipart_form_data = {"file": (file_name, file_buf, "application/json")}
            api.reports.import_ptrac_report(auth.base_url, auth.get_auth_headers(), client_id, multipart_form_data)
            log.success(f"Imported report '{report_name}' to client '{client_name}'")
            report_names_by_client_id.setdefault(client_id, []).append(report_name)
        except Exception as e:
            log.error(f"Could not import report '{report_name}'. Skipping...\n{e}")
            failed_reports.append(f"Client: {client_name} | Report: {report_name}")
            utils.save_json_as_ptrac_file(ptrac, folder_path="failed_ptracs")

    write_missing_clients_file(missing_client_names)
    if failed_reports:
        log.error(f"Finished importing with {len(failed_reports)} failed report(s). Failed PTRAC files were saved to failed_ptracs.")
    else:
        log.success(f"Finished importing {len(ptracs)} report(s).")


def determine_input_mode(args: argparse.Namespace) -> Optional[str]:
    """
    Decide whether to process a single file or a folder of files.

    - Both provided + interactive: prompt for "file" or "folder".
    - Both provided + non-interactive: warn and use file mode (smaller blast radius).
    - Only one provided: use that mode.
    - Neither provided: return None.
    """
    if args.data_file_path and args.data_folder_path:
        message = "Both data_file_path and data_folder_path were provided. Only one should have a value."
        if input.is_interactive_mode():
            log.warning(f"{message} Prompting for the intended input mode.")
            selected_mode = input.user_options(
                "Choose which input mode to use",
                retry_msg="Please choose either file or folder.",
                options=["file", "folder"],
            )
            log.info(f"Using {selected_mode} mode after interactive confirmation.")
            return selected_mode

        log.warning(f"{message} Non-interactive mode will use data_file_path to minimize blast radius.")
        return "file"

    if args.data_file_path:
        return "file"
    if args.data_folder_path:
        return "folder"
    return None


def get_input_file_paths(args: argparse.Namespace, spec) -> List[str]:
    """
    Resolve the list of input files to process for the chosen input mode.

    Folder-mode discovery is declared by each mapping spec.
    """
    input_mode = determine_input_mode(args)

    if input_mode == "file":
        return [args.data_file_path]

    if input_mode != "folder":
        return []

    return spec.find_input_files_function(args.data_folder_path)


def get_template_doc_id(items: list, requested_name: str, display_name: str, error_name: str) -> str:
    matches = []
    for item in items:
        data_item = item.get("data") if isinstance(item, dict) else None
        if not isinstance(data_item, dict):
            continue
        if data_item.get("template_name") == requested_name:
            matches.append(data_item)

    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {error_name} named '{requested_name}', found {len(matches)}")

    doc_id = matches[0].get("doc_id")
    if not doc_id:
        raise RuntimeError(f"{display_name} named '{requested_name}' is missing doc_id")
    return doc_id


def resolve_template_ids(args: argparse.Namespace) -> tuple:
    auth = Auth(args)
    auth.handle_authentication()
    report_template_id = ""
    findings_layout_id = ""

    if args.report_template_name:
        response = api._templates.report_templates.list_report_templates(auth.base_url, auth.get_auth_headers(), auth.tenant_id)
        templates = response.json if getattr(response, "json", None) and isinstance(response.json, list) else []
        report_template_id = get_template_doc_id(templates, args.report_template_name, "Report template", "report template")

    if args.findings_layout_name:
        response = api._templates.findings_templateslayouts.list_findings_templates(auth.base_url, auth.get_auth_headers())
        layouts = response.json if getattr(response, "json", None) and isinstance(response.json, list) else []
        findings_layout_id = get_template_doc_id(layouts, args.findings_layout_name, "Finding layout", "finding layout")

    return report_template_id, findings_layout_id


def get_cached_template_ids(args: argparse.Namespace) -> tuple:
    cache_key = (args.report_template_name, args.findings_layout_name)
    cached_settings = getattr(args, "_resolved_template_settings", None)
    if cached_settings and cached_settings[0] == cache_key:
        return cached_settings[1]

    template_ids = resolve_template_ids(args)
    setattr(args, "_resolved_template_settings", (cache_key, template_ids))
    return template_ids


def apply_template_settings(parser: CSVParser, args: argparse.Namespace) -> None:
    if not args.report_template_name and not args.findings_layout_name:
        return None

    try:
        report_template_id, findings_layout_id = get_cached_template_ids(args)
    except Exception as e:
        message = (
            "Could not resolve requested report template or finding layout. "
            "Generated PTRACs will not include the intended template/layout IDs."
        )
        if args.force_generate_ptrac:
            log.warning(f"{message}\n{e}")
            return None
        log.warning(f"{message}\nUse --force-generate-ptrac to generate PTRACs anyway.\n{e}")
        raise

    if report_template_id:
        parser.report_template["template"] = report_template_id
    if findings_layout_id:
        parser.report_template["fields_template"] = findings_layout_id
    return None


def process_input_file(data_file_path: str, map_type: str, spec, args: argparse.Namespace) -> list:
    """
    Process a single input file end-to-end and return its generated PTRAC data.
    """
    parser = CSVParser(header_mapping=spec.mapping)
    parser.enable_rich_text_processing = getattr(spec, "enable_rich_text_processing", False)
    handle_load_api_version(args.api_version, parser)

    # need to generate mapping from header file after spec is resolved and parser created for easier access to parser mapping keys
    if map_type == mappings.MapType.HEADER_MAPPING.value:
        header_file = mappings.load_header_mapping_file(args.headers_file_path)
        parser.csv_headers_mapping = mappings.build_mapping_from_header_file(header_file, parser)

    apply_template_settings(parser, args)

    log.info(f"Processing file '{data_file_path}' with mapping '{map_type}'")
    loaded_file = spec.load_data_function(data_file_path)
    if not spec.verify_function(loaded_file):
        raise ValueError(f"Data file is not valid: {data_file_path}")

    temp_csv = spec.temp_csv_function(loaded_file, parser)
    # debug: uncomment to write the intermediate mapped CSV (UTF-8) beside the input file
    # save_temp_csv_for_debug(temp_csv, f"{os.path.splitext(data_file_path)[0]}_temp_mapped.csv")
    load_parser_mappings_from_data_file(temp_csv, parser)
    load_data_into_parser(temp_csv, parser)

    finding_merge_strategy = (
        args.finding_merge_strategy
        if args.finding_merge_strategy != "none"
        else getattr(spec, "default_finding_merge_strategy", None)
    )
    if finding_merge_strategy:
        parser.set_finding_merge_strategy(finding_merge_strategy)

    if not parser.parse_data():
        raise RuntimeError(f"Parser failed for file: {data_file_path}")

    parser.display_parser_results()
    return parser.generate_ptrac_json_data()


def run(args: argparse.Namespace):
    map_type = args.type or (mappings.MapType.HEADER_MAPPING.value if args.headers_file_path else None)
    if map_type is None:
        log.critical("No mapping type provided. Use --type or provide headers_file_path in config.yaml.")
        exit(1)

    spec = mappings.resolve(map_type)
    input_file_paths = get_input_file_paths(args, spec)
    if not input_file_paths:
        log.critical("No input files found. Use --data-file-path or --data-folder-path.")
        exit(1)

    all_ptracs = []
    failed_files = []
    for data_file_path in input_file_paths:
        try:
            all_ptracs.extend(process_input_file(data_file_path, map_type, spec, args))
        except Exception as e:
            log.error(f"Could not process input file '{data_file_path}'. Skipping...\n{e}")
            failed_files.append(data_file_path)

    if not all_ptracs:
        log.critical("No PTRAC data was generated. Exiting...")
        exit(1)

    if failed_files:
        log.warning(f"PTRAC creation completed with {len(failed_files)} skipped input file(s): {failed_files}")

    all_ptracs = filter_ptracs_by_client_name(all_ptracs, getattr(args, "limit_to_client_name", ""))
    if not all_ptracs:
        log.critical("No PTRAC data matched the requested client-name filter. Exiting...")
        exit(1)

    if args.import_to_plextrac:
        import_ptracs_to_plextrac(all_ptracs, args)
        return None

    os.makedirs(args.output_dir, exist_ok=True)
    for ptrac in all_ptracs:
        utils.save_json_as_ptrac_file(ptrac, folder_path=args.output_dir)
    log.info(f"PTRAC creation complete. File(s) can be found in '{args.output_dir}' folder.")
    return None


if __name__ == "__main__":
    for i in settings.script_info:
        print(i)

    input.set_interactive_mode(settings.interactive)
    run(parse_args())
