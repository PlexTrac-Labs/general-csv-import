
from enum import Enum
from typing import List, Dict, Any, Union, Optional

from utils.input_utils import LoadedJSONData, LoadedCSVData
import utils.input_utils as input
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


# region ---- enum that bundles everything -------------------------------------------
class MapType(str, Enum):
    EXAMPLE_CSV = "example_csv"
    EXAMPLE_JSON = "example_json"
    HEADER_MAPPING = "header_mapping"

class _MapSpec:
    """Lightweight container to provide .mapping / .load_data_function / .verify_function / .temp_csv_function."""
    __slots__ = ("mapping", "load_data_function", "verify_function", "temp_csv_function")
    def __init__(self, mapping, load_data_function, verify_function, temp_csv_function):
        self.mapping = mapping
        self.load_data_function = load_data_function
        self.verify_function = verify_function
        self.temp_csv_function = temp_csv_function

EXAMPLE_CSV = _MapSpec(
    mapping=example_csv_template_mapping,
    load_data_function=load_data_file_general_csv,
    verify_function=verify_example_csv_payload,
    temp_csv_function=create_temp_data_csv_example_csv,
)

EXAMPLE_JSON = _MapSpec(
    mapping=example_json_template_mapping,
    load_data_function=load_data_file_general_json,
    verify_function=verify_example_json_payload,
    temp_csv_function=create_temp_data_csv_example_json,
)

HEADER_MAPPING = _MapSpec(
    mapping={},
    load_data_function=load_data_file_general_csv,
    verify_function=verify_header_mapping_payload,
    temp_csv_function=create_temp_data_csv_header_mapping,
)

def resolve(map_type_str: str) -> _MapSpec:
    if map_type_str == MapType.EXAMPLE_CSV.value:
        return EXAMPLE_CSV
    if map_type_str == MapType.EXAMPLE_JSON.value:
        return EXAMPLE_JSON
    if map_type_str == MapType.HEADER_MAPPING.value:
        return HEADER_MAPPING
    raise ValueError(f"Unknown mapping type: {map_type_str}")
# endregion
