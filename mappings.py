import glob
import os
from enum import Enum
from typing import List, Dict, Any, Union, Optional

from utils.input_utils import LoadedJSONData, LoadedCSVData
import utils.input_utils as input
import utils.general_utils as utils
import mapping_utils.dradis_utils as dradis
from mapping_utils.dradis_utils import LoadedDradisData
from csv_parser import CSVParser
import utils.log_handler as logger
log = logger.log

# region MAPPINGS -------------------------------------------
# the header is the name of the column in the temp CSV file
# the mapping_key is the key in the CSVParser.data_mapping dictionary

# the header must be the same as the key
# for mappings that require a label in addition to the data value, the header will be used as the label

# "Id": {
#     "header": "Id",
#     "mapping_key": "finding_title",
#     "col_index": None
# }

example_csv_template_mapping = {
    "title": {
        "header": "title",
        "mapping_key": "finding_title",
        "col_index": None
    },
    "severity": {
        "header": "severity",
        "mapping_key": "finding_severity",
        "col_index": None
    },
    "status": {
        "header": "status",
        "mapping_key": "finding_status",
        "col_index": None
    },
    "description": {
        "header": "description",
        "mapping_key": "finding_description",
        "col_index": None
    },
    "recommendations": {
        "header": "recommendations",
        "mapping_key": "finding_recommendations",
        "col_index": None
    },
    "references": {
        "header": "references",
        "mapping_key": "finding_references",
        "col_index": None
    },
    "asset_name": {
        "header": "asset_name",
        "mapping_key": "asset_name",
        "col_index": None
    },
    "evidence": {
        "header": "evidence",
        "mapping_key": "affected_asset_evidence",
        "col_index": None
    },
    "tags": {
        "header": "tags",
        "mapping_key": "finding_multi_tag",
        "col_index": None
    },
    "report_name": {
        "header": "report_name",
        "mapping_key": "report_name",
        "col_index": None
    },
    "client_name": {
        "header": "client_name",
        "mapping_key": "client_name",
        "col_index": None
    }
}

example_json_template_mapping = {
    "title": {
        "header": "title",
        "mapping_key": "finding_title",
        "col_index": None
    },
    "severity": {
        "header": "severity",
        "mapping_key": "finding_severity",
        "col_index": None
    },
    "status": {
        "header": "status",
        "mapping_key": "finding_status",
        "col_index": None
    },
    "description": {
        "header": "description",
        "mapping_key": "finding_description",
        "col_index": None
    },
    "recommendations": {
        "header": "recommendations",
        "mapping_key": "finding_recommendations",
        "col_index": None
    },
    "references": {
        "header": "references",
        "mapping_key": "finding_references",
        "col_index": None
    },
    "affected_assets": {
        "header": "affected_assets",
        "mapping_key": "asset_multi_name",
        "col_index": None
    },
    "tags": {
        "header": "tags",
        "mapping_key": "finding_multi_tag",
        "col_index": None
    },
    "report_name": {
        "header": "report_name",
        "mapping_key": "report_name",
        "col_index": None
    },
    "client_name": {
        "header": "client_name",
        "mapping_key": "client_name",
        "col_index": None
    }
}

# Generic, non-proprietary scaffold mapping for a Dradis CSV + ZIP/XML export.
# It is intentionally generic: it shows how a Dradis mapping is assembled and is
# the safe base example for building real (customer-specific) Dradis mappings.
# Do NOT add customer-specific fields, property names, or conditional tags here.
#
# Report narratives and custom fields share a mapping_key but use unique headers
# (the header becomes the PlexTrac label). Appendix/observation/exec-summary
# narratives are added dynamically while building the temp CSV.
example_dradis_csv_template_mapping = {
    # client / report
    "client_name": {"header": "client_name", "mapping_key": "client_name", "col_index": None},
    "report_name": {"header": "report_name", "mapping_key": "report_name", "col_index": None},
    "report_date": {"header": "report_date", "mapping_key": "report_start_date", "col_index": None},
    "Report Version": {"header": "Report Version", "mapping_key": "report_custom_field", "col_index": None},
    "report_tags": {"header": "report_tags", "mapping_key": "report_multi_tag", "col_index": None},
    # report narratives (static groups; dynamic appendix/observation added later)
    "Introduction": {"header": "Introduction", "mapping_key": "report_narrative", "col_index": None},
    "Overview": {"header": "Overview", "mapping_key": "report_narrative", "col_index": None},
    "Executive Summary": {"header": "Executive Summary", "mapping_key": "report_narrative", "col_index": None},
    "Observations": {"header": "Observations", "mapping_key": "report_narrative", "col_index": None},
    "Limitations": {"header": "Limitations", "mapping_key": "report_narrative", "col_index": None},
    "Out Of Scope": {"header": "Out Of Scope", "mapping_key": "report_narrative", "col_index": None},
    # finding fields
    "title": {"header": "title", "mapping_key": "finding_title", "col_index": None},
    "severity": {"header": "severity", "mapping_key": "finding_severity", "col_index": None},
    "status": {"header": "status", "mapping_key": "finding_status", "col_index": None},
    "description": {"header": "description", "mapping_key": "finding_description", "col_index": None},
    "Impact": {"header": "Impact", "mapping_key": "finding_custom_field", "col_index": None},
    "Likelihood": {"header": "Likelihood", "mapping_key": "finding_custom_field", "col_index": None},
    "recommendations": {"header": "recommendations", "mapping_key": "finding_recommendations", "col_index": None},
    "references": {"header": "references", "mapping_key": "finding_references", "col_index": None},
    "cvss_vector": {"header": "cvss_vector", "mapping_key": "finding_cvss3_1_vector", "col_index": None},
    "cvss_overall": {"header": "cvss_overall", "mapping_key": "finding_cvss3_1_overall", "col_index": None},
    "cwe": {"header": "cwe", "mapping_key": "finding_cwe", "col_index": None},
    "asset_name": {"header": "asset_name", "mapping_key": "asset_name", "col_index": None},
    "Evidence": {"header": "Evidence", "mapping_key": "affected_asset_evidence", "col_index": None},
    "tags": {"header": "tags", "mapping_key": "finding_multi_tag", "col_index": None},
}

example_dradis_zip_template_mapping = {
    "client_name": {"header": "client_name", "mapping_key": "client_name", "col_index": None},
    "report_name": {"header": "report_name", "mapping_key": "report_name", "col_index": None},
    "report_tags": {"header": "report_tags", "mapping_key": "report_multi_tag", "col_index": None},
    "Introduction": {"header": "Introduction", "mapping_key": "report_narrative", "col_index": None},
    "Executive Summary": {"header": "Executive Summary", "mapping_key": "report_narrative", "col_index": None},
    "title": {"header": "title", "mapping_key": "finding_title", "col_index": None},
    "severity": {"header": "severity", "mapping_key": "finding_severity", "col_index": None},
    "status": {"header": "status", "mapping_key": "finding_status", "col_index": None},
    "description": {"header": "description", "mapping_key": "finding_description", "col_index": None},
    "recommendations": {"header": "recommendations", "mapping_key": "finding_recommendations", "col_index": None},
    "references": {"header": "references", "mapping_key": "finding_references", "col_index": None},
    "cvss_vector": {"header": "cvss_vector", "mapping_key": "finding_cvss3_1_vector", "col_index": None},
    "asset_name": {"header": "asset_name", "mapping_key": "asset_name", "col_index": None},
    "affected_asset_location_url": {
        "header": "affected_asset_location_url",
        "mapping_key": "affected_asset_location_url",
        "col_index": None,
    },
    "affected_asset_port_number": {
        "header": "affected_asset_port_number",
        "mapping_key": "affected_asset_port_number",
        "col_index": None,
    },
    "affected_asset_port_protocol": {
        "header": "affected_asset_port_protocol",
        "mapping_key": "affected_asset_port_protocol",
        "col_index": None,
    },
    "tags": {"header": "tags", "mapping_key": "finding_multi_tag", "col_index": None},
}

# endregion ---


# region load data file functions
def load_data_file_general_csv(data_file_path:str = "") -> LoadedCSVData:
    """
    Loads a CSV file containing data to be imported in the script

    :param data_file_path: filepath to file containing data to import, defaults to ""
    :type data_file_path: str, optional - will exit if not supplied
    :return: raw data loaded from file
    :rtype: LoadedCSVData
    """
    return input.load_csv_data("Enter file path to custom scan CSV file to import", csv_file_path=data_file_path)

def load_header_mapping_file(headers_file_path: str = "") -> LoadedCSVData:
    return input.load_csv_data("Enter file path to header mapping CSV file", csv_file_path=headers_file_path)

def load_data_file_general_json(data_file_path:str = "") -> LoadedJSONData:
    """
    Loads a JSON file containing data to be imported in the script

    :param data_file_path: filepath to file containing data to import, defaults to ""
    :type data_file_path: str, optional - will exit if not supplied
    :return: raw data loaded from file
    :rtype: LoadedJSONData
    """
    return input.load_json_data("Enter file path to custom scan JSON file to import", json_file_path=data_file_path)

def load_data_file_example_dradis_csv(data_file_path: str = "") -> LoadedDradisData:
    """
    Loads a Dradis CSV export and its same-basename ZIP file (containing
    ``dradis-repository.xml``) into a normalized ``LoadedDradisData`` structure.

    :param data_file_path: filepath to the Dradis CSV export
    :type data_file_path: str
    :return: normalized Dradis data
    :rtype: LoadedDradisData
    """
    if not data_file_path:
        data_file_path = input.prompt_user("Enter file path to Dradis CSV export to import")
    return dradis.load_dradis_pair(data_file_path)


def load_data_file_example_dradis_zip(data_file_path: str = "") -> LoadedDradisData:
    """Load a ZIP/XML-only Dradis export for the graph-driven example mapping."""
    if not data_file_path:
        data_file_path = input.prompt_user("Enter file path to Dradis ZIP export to import")
    return dradis.load_dradis_zip(data_file_path)

# endregion ---


# region verify functions -------------------------------------------
def verify_example_csv_payload(loaded_file_data:LoadedCSVData) -> bool:
    """
    Checks that the loaded CSV data file is valid for the script

    Example headers:
    "client_name", "report_name", "title", "severity", "status", "description"

    :param loaded_file_data: object of returned loaded data from `load_data_file_X()`
    :type loaded_file_data: LoadedCSVData
    :return: whether the file is valid
    :rtype: bool
    """
    csv_data = loaded_file_data.csv
    # Shape/type checks
    if not isinstance(csv_data, list) or any(not isinstance(row, list) for row in csv_data):
        log.critical("verify_example_csv_payload: top-level data is not a List[List[str]]")
        return False
    if not csv_data:
        log.critical("verify_example_csv_payload: no data in CSV, missing header row")
        return False

    # Header value checks
    headers = loaded_file_data.headers
    required_headers = [
        "client_name", "report_name", "title", "severity", "status", "description"
    ]
    missing = [h for h in required_headers if h not in headers]
    if missing:
        log.critical(f"verify_example_csv_payload: missing required headers: {missing}")
        return False

    # At least one data row, not including header row
    if len(csv_data) < 2:
        log.critical("verify_example_csv_payload: no data rows present")
        return False

    return True

def verify_header_mapping_payload(loaded_file_data: LoadedCSVData) -> bool:
    csv_data = loaded_file_data.csv
    if not isinstance(csv_data, list) or any(not isinstance(row, list) for row in csv_data):
        log.critical("verify_header_mapping_payload: top-level data is not a List[List[str]]")
        return False
    if len(csv_data) < 2:
        log.critical("verify_header_mapping_payload: CSV must include a header row and at least one data row")
        return False
    return True

def verify_example_json_payload(loaded_file_data:LoadedJSONData) -> bool:
    """
    Checks that the loaded JSON data file is valid for the script

    Example: Validation rules setup for a .ptrac file

    :param loaded_file_data: object of returned loaded data from `load_data_file_X()`
    :type loaded_file_data: LoadedJSONData
    :return: whether the file is valid
    :rtype: bool
    """
    data = loaded_file_data.data
    # Shape/type checks
    if not isinstance(data, dict):
        log.critical("verify_example_json_payload: top-level data is not a dict")
        return False
    if not data:
        log.critical("verify_example_json_payload: no data in JSON")
        return False

    # Data value checks
    required_root_keys = ["report_info", "flaws_array", "summary", "client_info"]
    missing_keys = [k for k in required_root_keys if k not in data]
    if missing_keys:
        log.critical(f"verify_example_json_payload: missing required root keys: {missing_keys}")
        return False
    
    required_flaws_array_keys = ["title", "severity", "status", "description"]
    for i, item in enumerate(data["flaws_array"]):
        missing_keys = [k for k in required_flaws_array_keys if k not in item]
        if missing_keys:
            log.critical(f"verify_example_json_payload: finding at index {i} missing required keys: {missing_keys}")
            return False
    
    return True

def verify_example_dradis_csv_payload(loaded_file_data: LoadedDradisData) -> bool:
    """
    Checks that the loaded Dradis data is valid for the scaffold mapping.

    Requires CSV headers, at least one data row, at least one XML node, and at
    least one content block.

    :param loaded_file_data: object returned from `load_data_file_example_dradis_csv`
    :type loaded_file_data: LoadedDradisData
    :return: whether the data is valid
    :rtype: bool
    """
    if not isinstance(loaded_file_data, LoadedDradisData):
        log.critical("verify_example_dradis_csv_payload: loaded data is not LoadedDradisData")
        return False
    if not loaded_file_data.headers:
        log.critical("verify_example_dradis_csv_payload: CSV has no headers")
        return False
    if not loaded_file_data.row_dicts:
        log.critical("verify_example_dradis_csv_payload: CSV has no data rows")
        return False
    if not loaded_file_data.nodes:
        log.critical("verify_example_dradis_csv_payload: dradis-repository.xml has no nodes")
        return False
    if not loaded_file_data.content_blocks:
        log.critical("verify_example_dradis_csv_payload: dradis-repository.xml has no content blocks")
        return False
    return True


def verify_example_dradis_zip_payload(loaded_file_data: LoadedDradisData) -> bool:
    """Validate the ZIP/XML object graph required by the graph-driven example."""
    if not isinstance(loaded_file_data, LoadedDradisData):
        log.critical("verify_example_dradis_zip_payload: loaded data is not LoadedDradisData")
        return False
    if not loaded_file_data.nodes:
        log.critical("verify_example_dradis_zip_payload: missing Dradis nodes")
        return False
    if not loaded_file_data.issues:
        log.critical("verify_example_dradis_zip_payload: missing Dradis issues")
        return False
    return True

# endregion ---


# region temp csv functions -------------------------------------------
# helper functions for create_temp_csv functions
def hidx(temp_csv_headers: List[str], name: str) -> Union[int, None]:
    """
    Quick header index helper function for create_temp_csv functions.
    
    :param temp_csv_headers: List of CSV headers to search in
    :type temp_csv_headers: List[str]
    :param name: Header name to find index for
    :type name: str
    :return: Index of header or None if not found
    :rtype: Union[int, None]
    """
    try:
        return temp_csv_headers.index(name)
    except ValueError:
        return None

def set_field(temp_csv_headers: List[str], row: List[str], header: str, value: Any):
    """
    Row setter helper function for create_temp_csv functions.
    
    :param temp_csv_headers: List of CSV headers to search in
    :type temp_csv_headers: List[str]
    :param row: Row to set field in
    :type row: List[str]
    :param header: Header name to set
    :type header: str
    :param value: Value to set
    :type value: Any
    """
    i = hidx(temp_csv_headers, header)
    if i is not None:
        row[i] = "" if value is None else str(value)

def get_value(loaded_headers: List[str], row: Union[str, List[str]], header: str) -> str:
    """
    Get value helper function for create_temp_csv functions.
    
    :param loaded_headers: List of loaded CSV headers to search in
    :type loaded_headers: List[str]
    :param row: Row to get value from
    :type row: Union[str, List[str]]
    :param header: Header name to get value for
    :type header: str
    :return: Value from row or empty string if not found
    :rtype: str
    """
    try:
        i = loaded_headers.index(header)
    except ValueError:
        log.warning(f"Could not get value for column with header '{header}'")
        return ""
    if isinstance(row, str):
        return row
    return str(row[i]) if row[i] is not None else ""


def create_temp_data_csv_example_csv(loaded_file_data: LoadedCSVData, parser: CSVParser) -> List[list]:
    """
    Converts Example CSV data to a temporary CSV format compatible with the parser.

    :param loaded_file_data: object of returned loaded data from `load_data_file_X()`
    :type loaded_file_data: LoadedCSVData
    :param parser: instance of CSVParser that data will be loaded into
    :type parser: CSVParser
    :return: temp generated CSV
    :rtype: List[list]
    """
    loaded_data = loaded_file_data.data
    loaded_headers = loaded_file_data.headers

    temp_csv_headers = parser.get_csv_headers()
    temp_csv: List[List[str]] = [temp_csv_headers]

    # helpers
    def handle_severity(severity: str) -> str:
        accepted_severities = ["Critical", "High", "Medium", "Low", "Informational"]
        if severity not in accepted_severities:
            log.warning(f"Severity '{severity}' is not a valid severity. Must be in the list {accepted_severities}. Defaulting to 'Informational'...")
            return "Informational"
        return severity

    def handle_status(status: str) -> str:
        accepted_statuses = ["Open", "Closed", "In Progress"]
        if status not in accepted_statuses:
            log.warning(f"Status '{status}' is not a valid status. Must be in the list {accepted_statuses}. Defaulting to 'Open'...")
            return "Open"
        return status
    
    def handle_tags(tags: str) -> str:
        if not isinstance(tags, str) or not tags:
            tag_array = []
        else:
            tag_array = tags.split(',')
            tag_array = [tag.strip() for tag in tag_array]
        tag_array.append("example_csv")
        return ", ".join(tag_array)

    for i, loaded_row in enumerate(loaded_data):
        # valid row checks
        title = get_value(loaded_headers, loaded_row, "title")
        if title == "":
            log.error(f"Row {i} has no title. Cannot create finding. Skipping...")
            continue
        
        client_name = get_value(loaded_headers, loaded_row, "client_name")
        if client_name == "":
            log.error(f"Row {i} has no client name. Cannot create finding. Skipping...")
            continue
        
        report_name = get_value(loaded_headers, loaded_row, "report_name")
        if report_name == "":
            log.error(f"Row {i} has no report name. Cannot create finding. Skipping...")
            continue

        # seed row
        new_row = ["" for _ in range(len(temp_csv_headers))]

        set_field(temp_csv_headers, new_row, "title", title)
        set_field(temp_csv_headers, new_row, "severity", handle_severity(get_value(loaded_headers, loaded_row, "severity")))
        set_field(temp_csv_headers, new_row, "status", handle_status(get_value(loaded_headers, loaded_row, "status")))
        set_field(temp_csv_headers, new_row, "description", get_value(loaded_headers, loaded_row, "description"))
        set_field(temp_csv_headers, new_row, "recommendations", get_value(loaded_headers, loaded_row, "recommendations"))
        set_field(temp_csv_headers, new_row, "references", get_value(loaded_headers, loaded_row, "references"))
        set_field(temp_csv_headers, new_row, "asset_name", get_value(loaded_headers, loaded_row, "asset_name"))
        set_field(temp_csv_headers, new_row, "evidence", get_value(loaded_headers, loaded_row, "evidence"))
        set_field(temp_csv_headers, new_row, "tags", handle_tags(get_value(loaded_headers, loaded_row, "tags")))
        set_field(temp_csv_headers, new_row, "report_name", report_name)
        set_field(temp_csv_headers, new_row, "client_name", client_name)

        temp_csv.append(new_row)
    
    return temp_csv

def create_temp_data_csv_example_json(loaded_file_data: LoadedJSONData, parser: CSVParser) -> List[list]:
    """
    Converts Example JSON data to a temporary CSV format compatible with the parser.

    :param loaded_file_data: object of returned loaded data from `load_data_file_X()`
    :type loaded_file_data: LoadedJSONData
    :param parser: instance of CSVParser that data will be loaded into
    :type parser: CSVParser
    :return: temp generated CSV
    :rtype: List[list]
    """
    loaded_data = loaded_file_data.data

    temp_csv_headers = parser.get_csv_headers()
    temp_csv: List[List[str]] = [temp_csv_headers]

    # helpers
    def handle_severity(severity: str) -> str:
        accepted_severities = ["Critical", "High", "Medium", "Low", "Informational"]
        if severity not in accepted_severities:
            log.warning(f"Severity '{severity}' is not a valid severity. Must be in the list {accepted_severities}. Defaulting to 'Informational'...")
            return "Informational"
        return severity
    
    def handle_status(status: str) -> str:
        accepted_statuses = ["Open", "Closed", "In Progress"]
        if status not in accepted_statuses:
            log.warning(f"Status '{status}' is not a valid status. Must be in the list {accepted_statuses}. Defaulting to 'Open'...")
            return "Open"
        return status

    def handle_assets(affected_assets: Dict[str, dict]) -> str:
        if not isinstance(affected_assets, dict) or not affected_assets:
            asset_array = []
        else:
            asset_array = [asset["asset"].strip() for asset in affected_assets.values()]
        return ", ".join(asset_array)
    
    def handle_tags(tags: str) -> str:
        if not isinstance(tags, str) or not tags:
            tag_array = []
        else:
            tag_array = tags.split(',')
            tag_array = [tag.strip() for tag in tag_array]
        tag_array.append("example_json")
        return ", ".join(tag_array)

    # Get Client Data
    client_name = loaded_data["client_info"]["name"]

    # Get Report Data
    report_name = loaded_data["report_info"]["name"]

    for i, finding in enumerate(loaded_data["flaws_array"]):
        # valid object checks
        title = finding["title"]
        if title == "":
            log.error(f"Finding {i} has no title. Cannot create finding. Skipping...")
            continue
        
        # seed row
        new_row = ["" for _ in range(len(temp_csv_headers))]

        set_field(temp_csv_headers, new_row, "title", title)
        set_field(temp_csv_headers, new_row, "severity", handle_severity(finding["severity"]))
        set_field(temp_csv_headers, new_row, "status", handle_status(finding["status"]))
        set_field(temp_csv_headers, new_row, "description", finding["description"])
        set_field(temp_csv_headers, new_row, "recommendations", finding["recommendations"])
        set_field(temp_csv_headers, new_row, "references", finding["references"])
        set_field(temp_csv_headers, new_row, "affected_assets", handle_assets(finding["affected_assets"]))
        set_field(temp_csv_headers, new_row, "tags", handle_tags(finding["tags"]))
        set_field(temp_csv_headers, new_row, "report_name", report_name)
        set_field(temp_csv_headers, new_row, "client_name", client_name)

        temp_csv.append(new_row)
    
    return temp_csv

def create_temp_data_csv_header_mapping(loaded_file_data: LoadedCSVData, parser: CSVParser) -> List[list]:
    return loaded_file_data.csv

def _add_dynamic_narrative_headers(parser: CSVParser, narratives: List[tuple]) -> None:
    """Add report narrative headers to the parser mapping before computing headers."""
    for label, _text in narratives:
        if label not in parser.csv_headers_mapping:
            parser.csv_headers_mapping[label] = {
                "header": label,
                "mapping_key": "report_narrative",
                "col_index": None,
            }

def create_temp_data_csv_example_dradis_csv(loaded_file_data: LoadedDradisData, parser: CSVParser) -> List[list]:
    """
    Converts a Dradis CSV + ZIP/XML export into a temporary CSV the generic
    parser already understands.

    This is intentionally a generic scaffold. It prefers structured XML issue
    sections and content blocks, falling back to CSV columns. Customer-specific
    field choices should live in a dedicated `dradis_<customer>` mapping, not here.

    :param loaded_file_data: normalized Dradis data
    :type loaded_file_data: LoadedDradisData
    :param parser: parser instance the temp CSV will be loaded into
    :type parser: CSVParser
    :return: temp generated CSV (header row + data rows)
    :rtype: List[list]
    """
    # the parser needs the paired ZIP to resolve embedded Dradis images
    parser.zip_file_path = loaded_file_data.zip_file_path

    nodes = loaded_file_data.nodes
    issues = loaded_file_data.issues
    content_blocks = loaded_file_data.content_blocks
    report_props = loaded_file_data.report_properties

    # build dynamic report narratives from content blocks and register headers
    dynamic_narratives = (
        dradis.get_dradis_executive_summary_narratives(content_blocks)
        + dradis.get_dradis_observation_narratives(content_blocks)
        + dradis.get_dradis_appendix_narratives(content_blocks)
    )
    _add_dynamic_narrative_headers(parser, dynamic_narratives)

    temp_csv_headers = parser.get_csv_headers()
    temp_csv: List[List[str]] = [temp_csv_headers]

    # report-level values (repeated on each finding row; only applied once by the parser)
    report_name = dradis.first_value(
        dradis.get_property(report_props, ["report_title", "title", "name"]),
        os.path.splitext(os.path.basename(loaded_file_data.file_path))[0],
    )
    client_name = dradis.first_value(
        dradis.get_property(report_props, ["client", "client_name", "customer"]),
        "Dradis Import Client",
    )
    report_date = dradis.get_property(report_props, ["report_date", "date", "end_date"])
    report_version = dradis.get_property(report_props, ["version", "report_version"])

    static_narratives = {
        "Introduction": dradis.content_block_text(content_blocks, "Introduction"),
        "Overview": dradis.content_block_text(content_blocks, "Overview"),
        "Executive Summary": dradis.content_block_text(content_blocks, "Executive Summary"),
        "Observations": dradis.content_block_text(content_blocks, "Observations"),
        "Limitations": dradis.content_block_text(content_blocks, "Limitations"),
        "Out Of Scope": dradis.content_block_text(content_blocks, ["Out Of Scope", "Out of Scope"]),
    }

    target_node_label = dradis.get_dradis_target_node_label(nodes)

    for i, row in enumerate(loaded_file_data.row_dicts):
        issue = dradis.find_issue_for_row(row, issues) or dradis.get_single_dradis_issue(issues)
        sections = issue.get("sections", {}) if issue else {}

        title = dradis.first_value(
            sections.get("title", ""),
            issue.get("title", "") if issue else "",
            dradis.get_csv_value(row, ["Title", "Finding Name", "Vulnerability Name"]),
        )
        if not title:
            log.warning(f"Dradis row {i} has no resolvable finding title. Skipping...")
            continue

        new_row = ["" for _ in range(len(temp_csv_headers))]

        # report-level
        set_field(temp_csv_headers, new_row, "client_name", client_name)
        set_field(temp_csv_headers, new_row, "report_name", report_name)
        set_field(temp_csv_headers, new_row, "report_date", report_date)
        set_field(temp_csv_headers, new_row, "Report Version", report_version)
        set_field(temp_csv_headers, new_row, "report_tags", "example_dradis_csv")
        for label, text in static_narratives.items():
            set_field(temp_csv_headers, new_row, label, text)
        for label, text in dynamic_narratives:
            set_field(temp_csv_headers, new_row, label, text)

        # finding-level (prefer XML issue sections, fall back to CSV)
        severity = dradis.normalize_dradis_severity(dradis.first_value(
            sections.get("rating", ""), sections.get("severity", ""),
            dradis.get_csv_value(row, ["Rating", "Severity"]),
        ))
        status = dradis.normalize_dradis_status(dradis.first_value(
            sections.get("status", ""), dradis.get_csv_value(row, ["Status", "State"]),
        ))
        description = dradis.first_value(
            sections.get("description", ""), dradis.get_csv_value(row, ["Description"]),
        )
        impact = dradis.first_value(sections.get("impact", ""), dradis.get_csv_value(row, ["Impact"]))
        likelihood = dradis.first_value(sections.get("likelihood", ""), dradis.get_csv_value(row, ["Likelihood"]))
        recommendations = dradis.first_value(
            sections.get("recommendation", ""), sections.get("recommendations", ""),
            sections.get("remediation", ""), dradis.get_csv_value(row, ["Recommendation", "Recommendations", "Remediation"]),
        )
        references = dradis.first_value(
            sections.get("references", ""), dradis.get_csv_value(row, ["References", "Reference"]),
        )
        cvss_vector = dradis.first_value(
            sections.get("cvss_vector", ""), sections.get("cvss3_1_vector", ""),
            dradis.get_csv_value(row, ["CVSS Vector", "CVSS3.1 Vector", "CVSSVector"]),
        )
        cwe = dradis.first_value(sections.get("cwe", ""), dradis.get_csv_value(row, ["CWE"]))
        asset_name = dradis.first_value(
            dradis.get_csv_value(row, ["Affected Asset", "Asset", "Host", "Target"]), target_node_label,
        )
        evidence = dradis.first_value(
            sections.get("proofofconcept", ""), sections.get("proof_of_concept", ""),
            sections.get("evidence", ""), dradis.get_csv_value(row, ["ProofOfConcept", "Proof of Concept", "Evidence"]),
        )

        set_field(temp_csv_headers, new_row, "title", title)
        set_field(temp_csv_headers, new_row, "severity", severity)
        set_field(temp_csv_headers, new_row, "status", status)
        set_field(temp_csv_headers, new_row, "description", description)
        set_field(temp_csv_headers, new_row, "Impact", impact)
        set_field(temp_csv_headers, new_row, "Likelihood", likelihood)
        set_field(temp_csv_headers, new_row, "recommendations", recommendations)
        set_field(temp_csv_headers, new_row, "references", references)
        set_field(temp_csv_headers, new_row, "cwe", cwe)
        set_field(temp_csv_headers, new_row, "asset_name", asset_name)
        set_field(temp_csv_headers, new_row, "Evidence", evidence)
        set_field(temp_csv_headers, new_row, "tags", "example_dradis_csv")

        # CVSS: keep the vector and compute the overall base score when valid
        if cvss_vector:
            set_field(temp_csv_headers, new_row, "cvss_vector", cvss_vector)
            normalized_vector = cvss_vector[9:] if cvss_vector.startswith("CVSS:3.1/") else cvss_vector
            if utils.is_valid_cvss3_1_vector(normalized_vector):
                try:
                    set_field(temp_csv_headers, new_row, "cvss_overall", utils.calculate_cvss3_base_score(cvss_vector))
                except Exception as e:
                    log.warning(f"Could not calculate CVSS base score for '{cvss_vector}'. {e}")

        temp_csv.append(new_row)

    return temp_csv


def create_temp_data_csv_example_dradis_zip(loaded_file_data: LoadedDradisData, parser: CSVParser) -> List[list]:
    """
    Convert a Dradis ZIP/XML object graph into the parser's temporary CSV shape.

    The unit of import is an evidence record. Each evidence row links one issue to
    one asset; issues without evidence still emit a finding row.
    """
    parser.zip_file_path = loaded_file_data.zip_file_path

    temp_csv_headers = parser.get_csv_headers()
    temp_csv: List[List[str]] = [temp_csv_headers]
    properties = dradis.get_report_node_properties(loaded_file_data.nodes)

    client_name = dradis.get_property(
        properties,
        ["dradis.clientformal", "dradis.client", "dradis.clientshort"],
        "Dradis Client",
    )
    report_name = dradis.get_property(
        properties,
        ["dradis.application", "dradis.project", "dradis.appname"],
        "Dradis Report",
    )
    narratives = {
        "Introduction": dradis.content_block_text(loaded_file_data.content_blocks, "Introduction"),
        "Executive Summary": dradis.content_block_text(
            loaded_file_data.content_blocks,
            ["ExecutiveSummary", "ExecSummary", "Executive Summary"],
        ),
    }

    def seed_common_fields(new_row: List[str]) -> None:
        set_field(temp_csv_headers, new_row, "client_name", client_name)
        set_field(temp_csv_headers, new_row, "report_name", report_name)
        set_field(temp_csv_headers, new_row, "report_tags", "example_dradis_zip")
        for narrative_header, narrative_value in narratives.items():
            set_field(temp_csv_headers, new_row, narrative_header, narrative_value)

    evidence_records = dradis.get_dradis_evidence(loaded_file_data.nodes)
    issue_ids_with_evidence = {record["issue_id"] for record in evidence_records if record["issue_id"]}
    rows_plan: List[tuple] = []
    for record in evidence_records:
        issue = dradis.get_issue_by_id(loaded_file_data.issues, record["issue_id"])
        if issue is None:
            log.warning(
                f"example_dradis_zip evidence {record['evidence_id']} references unknown issue id "
                f"'{record['issue_id']}'. Skipping evidence..."
            )
            continue
        rows_plan.append((issue, record))

    for issue in loaded_file_data.issues:
        if str(issue.get("id", "")).strip() not in issue_ids_with_evidence:
            rows_plan.append((issue, None))

    for row_index, (issue, evidence) in enumerate(rows_plan):
        issue_sections = issue.get("sections", {})
        title = dradis.first_value(issue_sections.get("title", ""), issue.get("title", ""))
        if not title:
            log.error(f"example_dradis_zip row {row_index} has no finding title. Skipping...")
            continue

        new_row = ["" for _ in range(len(temp_csv_headers))]
        seed_common_fields(new_row)

        issue_state = ""
        raw_issue = issue.get("raw", {})
        if isinstance(raw_issue, dict):
            issue_state = raw_issue.get("state", "")

        set_field(temp_csv_headers, new_row, "title", title)
        set_field(temp_csv_headers, new_row, "severity", dradis.normalize_dradis_severity(issue_sections.get("rating", "")))
        set_field(temp_csv_headers, new_row, "status", dradis.normalize_dradis_status(issue_state))
        set_field(temp_csv_headers, new_row, "description", issue_sections.get("details", ""))
        set_field(temp_csv_headers, new_row, "recommendations", issue_sections.get("remediation", ""))
        set_field(temp_csv_headers, new_row, "references", issue_sections.get("references", ""))
        set_field(temp_csv_headers, new_row, "cvss_vector", issue_sections.get("cvssv3.vector", ""))

        if evidence is not None:
            evidence_sections = evidence.get("sections", {})
            set_field(temp_csv_headers, new_row, "asset_name", dradis.clean_dradis_node_label(evidence.get("node_label", "")))
            set_field(
                temp_csv_headers,
                new_row,
                "affected_asset_location_url",
                dradis.strip_textile_link_url(evidence_sections.get("vulnerable_target:_iporurl", "")),
            )
            set_field(temp_csv_headers, new_row, "affected_asset_port_number", evidence_sections.get("port", ""))
            set_field(temp_csv_headers, new_row, "affected_asset_port_protocol", evidence_sections.get("protocol", ""))

        set_field(temp_csv_headers, new_row, "tags", "example_dradis_zip")
        temp_csv.append(new_row)

    return temp_csv

def build_mapping_from_header_file(header_file: LoadedCSVData, parser: CSVParser) -> Dict[str, Dict[str, Any]]:
    mapping = {}
    mapping_keys = header_file.data[0] if header_file.data else []

    for index, header in enumerate(header_file.headers):
        mapping_key = mapping_keys[index].strip() if index < len(mapping_keys) and mapping_keys[index].strip() else "no_mapping"
        if mapping_key not in parser.get_data_mapping_ids():
            log.warning(f"Invalid mapping key '{mapping_key}' for header '{header}'. Marking as 'no_mapping'")
            mapping_key = "no_mapping"
        mapping[header] = {
            "header": header,
            "mapping_key": mapping_key,
            "col_index": index,
        }

    return mapping

# endregion ---


# region input discovery functions -------------------------------------------
def find_input_files_general_csv(folder_path: str) -> List[str]:
    return sorted(glob.glob(os.path.join(folder_path, "*.csv")))


def find_input_files_general_json(folder_path: str) -> List[str]:
    return sorted(glob.glob(os.path.join(folder_path, "*.json")))


def find_input_files_dradis_pair(folder_path: str) -> List[str]:
    return dradis.find_dradis_csv_candidates(folder_path)


def find_input_files_dradis_zip(folder_path: str) -> List[str]:
    return dradis.find_dradis_zip_candidates(folder_path)
# endregion ---


# region ---- enum that bundles everything -------------------------------------------
class MapType(str, Enum):
    EXAMPLE_CSV = "example_csv"
    EXAMPLE_JSON = "example_json"
    EXAMPLE_DRADIS_CSV = "example_dradis_csv"
    EXAMPLE_DRADIS_ZIP = "example_dradis_zip"
    HEADER_MAPPING = "header_mapping"

class _MapSpec:
    """Lightweight container for a mapping's loading, validation, and run behavior."""
    __slots__ = (
        "mapping",
        "load_data_function",
        "verify_function",
        "temp_csv_function",
        "find_input_files_function",
        "default_finding_merge_strategy",
        "enable_rich_text_processing",
    )

    def __init__(
        self,
        mapping,
        load_data_function,
        verify_function,
        temp_csv_function,
        find_input_files_function,
        default_finding_merge_strategy=None,
        enable_rich_text_processing=False,
    ):
        self.mapping = mapping
        self.load_data_function = load_data_function
        self.verify_function = verify_function
        self.temp_csv_function = temp_csv_function
        self.find_input_files_function = find_input_files_function
        self.default_finding_merge_strategy = default_finding_merge_strategy
        self.enable_rich_text_processing = enable_rich_text_processing

EXAMPLE_CSV = _MapSpec(
    mapping=example_csv_template_mapping,
    load_data_function=load_data_file_general_csv,
    verify_function=verify_example_csv_payload,
    temp_csv_function=create_temp_data_csv_example_csv,
    find_input_files_function=find_input_files_general_csv,
)

EXAMPLE_JSON = _MapSpec(
    mapping=example_json_template_mapping,
    load_data_function=load_data_file_general_json,
    verify_function=verify_example_json_payload,
    temp_csv_function=create_temp_data_csv_example_json,
    find_input_files_function=find_input_files_general_json,
)

HEADER_MAPPING = _MapSpec(
    mapping={},
    load_data_function=load_data_file_general_csv,
    verify_function=verify_header_mapping_payload,
    temp_csv_function=create_temp_data_csv_header_mapping,
    find_input_files_function=find_input_files_general_csv,
)

EXAMPLE_DRADIS_CSV = _MapSpec(
    mapping=example_dradis_csv_template_mapping,
    load_data_function=load_data_file_example_dradis_csv,
    verify_function=verify_example_dradis_csv_payload,
    temp_csv_function=create_temp_data_csv_example_dradis_csv,
    find_input_files_function=find_input_files_dradis_pair,
    enable_rich_text_processing=True,
)

EXAMPLE_DRADIS_ZIP = _MapSpec(
    mapping=example_dradis_zip_template_mapping,
    load_data_function=load_data_file_example_dradis_zip,
    verify_function=verify_example_dradis_zip_payload,
    temp_csv_function=create_temp_data_csv_example_dradis_zip,
    find_input_files_function=find_input_files_dradis_zip,
    default_finding_merge_strategy="user_defined_fields",
    enable_rich_text_processing=True,
)

def resolve(map_type_str: str) -> _MapSpec:
    if map_type_str == MapType.EXAMPLE_CSV.value:
        return EXAMPLE_CSV
    if map_type_str == MapType.EXAMPLE_JSON.value:
        return EXAMPLE_JSON
    if map_type_str == MapType.HEADER_MAPPING.value:
        return HEADER_MAPPING
    if map_type_str == MapType.EXAMPLE_DRADIS_CSV.value:
        return EXAMPLE_DRADIS_CSV
    if map_type_str == MapType.EXAMPLE_DRADIS_ZIP.value:
        return EXAMPLE_DRADIS_ZIP
    raise ValueError(f"Unknown mapping type: {map_type_str}")
# endregion
