from typing import List
import argparse
import io
import json
import os

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


def load_parser_mappings_from_data_file(csv: List[list], parser: CSVParser) -> bool:
    """
    Match generated temp-CSV headers to the injected parser header mapping.
    """
    headers = csv[0]

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


def load_data_into_parser(csv: List[list], parser: CSVParser) -> None:
    """
    Load CSV-like data rows into the parser, excluding the header row.
    """
    parser.csv_data = csv[1:]
    log.success("Loaded data into parser instance")


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="General CSV Import template parser")
    parser.add_argument("-i", "--input", required=True, help="Path to input data file.")
    parser.add_argument(
        "--type",
        choices=[map_type.value for map_type in mappings.MapType],
        required=True,
        help="Parser mapping type to use.",
    )
    parser.add_argument("--api-version", required=True, help="PlexTrac API version, e.g. '2.19.0'.")
    parser.add_argument("--client-name", default="", help="Optional client name override for custom mappings.")
    parser.add_argument("--report-name", default="", help="Optional report name override for custom mappings.")
    parser.add_argument(
        "--finding-merge-strategy",
        choices=["none", "title", "user_defined_fields", "all_fields"],
        default="none",
        help="Optional finding merge strategy.",
    )
    parser.add_argument("--output-dir", default="exported_ptracs", help="Directory for generated PTRAC files.")
    parser.add_argument("--import-to-plextrac", action="store_true", help="Import generated PTRAC reports into PlexTrac.")
    parser.add_argument("--instance-url", default="", help="PlexTrac instance URL for import mode.")
    parser.add_argument("-u", "--username", default="", help="PlexTrac username for import mode.")
    parser.add_argument("-p", "--password", default="", help="PlexTrac password for import mode.")
    parser.add_argument("--return-json", action="store_true", help=argparse.SUPPRESS)
    return parser


def import_ptracs_to_plextrac(ptracs: list, args: argparse.Namespace) -> None:
    auth = Auth(args)
    auth.handle_authentication()

    clients = []
    if not data.get_page_of_clients(clients=clients, auth=auth):
        log.critical("Could not load clients from PlexTrac. Exiting...")
        exit(1)
    if len(clients) < 1:
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
            log.error(f"Mapped client name '{client_name}' does not exist in PlexTrac. Skipping...")
            failed_reports.append(f"Client: {client_name} | Report: {report_name}")
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
        except Exception as e:
            log.error(f"Could not import report '{report_name}'. Skipping...\n{e}")
            failed_reports.append(f"Client: {client_name} | Report: {report_name}")
            utils.save_json_as_ptrac_file(ptrac, folder_path="failed_ptracs")

    if failed_reports:
        log.error(f"Finished importing with {len(failed_reports)} failed report(s). Failed PTRAC files were saved to failed_ptracs.")
    else:
        log.success(f"Finished importing {len(ptracs)} report(s).")


def run(args: argparse.Namespace):
    spec = mappings.resolve(args.type)
    parser = CSVParser(header_mapping=spec.mapping)
    handle_load_api_version(args.api_version, parser)

    log.info(f"Processing file '{args.input}' with mapping '{args.type}'")
    loaded_file = spec.load_data_function(args.input)
    if not spec.verify_function(loaded_file):
        log.critical("Data file is not valid. Exiting...")
        exit(1)

    temp_csv = spec.temp_csv_function(loaded_file, parser)
    load_parser_mappings_from_data_file(temp_csv, parser)
    load_data_into_parser(temp_csv, parser)

    if args.finding_merge_strategy != "none":
        parser.set_finding_merge_strategy(args.finding_merge_strategy)

    if not parser.parse_data():
        log.critical("Parser ran into an unexpected error during parsing. Exiting...")
        exit(1)

    parser.display_parser_results()

    if args.return_json:
        return parser.save_data_as_ptrac(return_ptrac_jsons=True)

    if args.import_to_plextrac:
        ptracs = parser.save_data_as_ptrac(return_ptrac_jsons=True)
        import_ptracs_to_plextrac(ptracs, args)
        return None

    os.makedirs(args.output_dir, exist_ok=True)
    parser.save_data_as_ptrac(folder_path=args.output_dir)
    log.info(f"PTRAC creation complete. File(s) can be found in '{args.output_dir}' folder.")
    return None


if __name__ == "__main__":
    for i in settings.script_info:
        print(i)

    input.set_interactive_mode(False)
    arg_parser = create_argument_parser()
    run(arg_parser.parse_args())
