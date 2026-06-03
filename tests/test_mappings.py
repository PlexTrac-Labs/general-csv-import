import mappings
from csv_parser import CSVParser
from utils.input_utils import LoadedCSVData
from mapping_utils.dradis_utils import LoadedDradisData


def _make_loaded_dradis():
    return LoadedDradisData(
        file_path="Project1.csv",
        zip_file_path="Project1.zip",
        csv_rows=[["Title", "Severity", "Status", "Description"], ["SQL Injection", "Low", "closed", "csv desc"]],
        headers=["Title", "Severity", "Status", "Description"],
        row_dicts=[{"Title": "SQL Injection", "Severity": "Low", "Status": "closed", "Description": "csv desc"}],
        xml={},
        nodes=[
            {"label": "example.com", "properties": {}},
            {"label": "Report content", "properties": {}},
        ],
        issues=[{
            "title": "SQL Injection",
            "sections": {"title": "SQL Injection", "rating": "High", "description": "xml desc", "recommendation": "Use params"},
        }],
        content_blocks=[
            {"group": "Introduction", "title": "", "content": "intro", "sections": {"description": "Intro text"}},
            {"group": "Appendix", "title": "Methodology", "content": "appx", "sections": {"description": "appendix body"}},
        ],
        report_properties={"report_title": "Example Report", "client": "Acme", "report_date": "May 8, 2026"},
    )


def test_example_mapping_keys_exist_in_csv_parser_data_mapping():
    valid_mapping_keys = set(CSVParser().get_data_mapping_ids())

    for map_type in mappings.MapType:
        spec = mappings.resolve(map_type.value)
        invalid_keys = {
            header: item["mapping_key"]
            for header, item in spec.mapping.items()
            if item["mapping_key"] not in valid_mapping_keys
        }

        assert invalid_keys == {}


def test_resolve_returns_example_csv_spec():
    spec = mappings.resolve(mappings.MapType.EXAMPLE_CSV.value)

    assert spec.mapping is mappings.example_csv_template_mapping
    assert spec.load_data_function is mappings.load_data_file_general_csv
    assert spec.verify_function is mappings.verify_example_csv_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_example_csv


def test_resolve_returns_example_json_spec():
    spec = mappings.resolve(mappings.MapType.EXAMPLE_JSON.value)

    assert spec.mapping is mappings.example_json_template_mapping
    assert spec.load_data_function is mappings.load_data_file_general_json
    assert spec.verify_function is mappings.verify_example_json_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_example_json


def test_build_mapping_from_header_file_uses_customer_mapping_keys():
    parser = CSVParser()
    header_file = LoadedCSVData(
        file_path="header_mapping.csv",
        csv=[
            ["Finding", "Severity", "Unmapped"],
            ["finding_title", "finding_severity", ""],
        ],
        headers=["Finding", "Severity", "Unmapped"],
        data=[["finding_title", "finding_severity", ""]],
    )

    mapping = mappings.build_mapping_from_header_file(header_file, parser)

    assert mapping == {
        "Finding": {"header": "Finding", "mapping_key": "finding_title", "col_index": 0},
        "Severity": {"header": "Severity", "mapping_key": "finding_severity", "col_index": 1},
        "Unmapped": {"header": "Unmapped", "mapping_key": "no_mapping", "col_index": 2},
    }


def test_header_mapping_spec_returns_original_csv_as_temp_csv():
    spec = mappings.resolve(mappings.MapType.HEADER_MAPPING.value)
    loaded = LoadedCSVData(
        file_path="data.csv",
        csv=[["Finding"], ["SQL Injection"]],
        headers=["Finding"],
        data=[["SQL Injection"]],
    )

    assert spec.temp_csv_function(loaded, CSVParser()) == loaded.csv


def test_resolve_returns_dradis_example_spec():
    spec = mappings.resolve(mappings.MapType.DRADIS_EXAMPLE.value)

    assert spec.mapping is mappings.dradis_example_template_mapping
    assert spec.load_data_function is mappings.load_data_file_dradis_example
    assert spec.verify_function is mappings.verify_dradis_example_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_dradis_example


def test_verify_dradis_example_payload_requires_headers_rows_nodes_and_blocks():
    valid = _make_loaded_dradis()
    assert mappings.verify_dradis_example_payload(valid) is True

    no_headers = _make_loaded_dradis()
    no_headers.headers = []
    assert mappings.verify_dradis_example_payload(no_headers) is False

    no_rows = _make_loaded_dradis()
    no_rows.row_dicts = []
    assert mappings.verify_dradis_example_payload(no_rows) is False

    no_nodes = _make_loaded_dradis()
    no_nodes.nodes = []
    assert mappings.verify_dradis_example_payload(no_nodes) is False

    no_blocks = _make_loaded_dradis()
    no_blocks.content_blocks = []
    assert mappings.verify_dradis_example_payload(no_blocks) is False


def test_create_temp_data_csv_dradis_example_builds_generic_fields():
    loaded = _make_loaded_dradis()
    parser = CSVParser(header_mapping=mappings.dradis_example_template_mapping)

    temp_csv = mappings.create_temp_data_csv_dradis_example(loaded, parser)

    headers = temp_csv[0]
    row = temp_csv[1]

    def value(name):
        return row[headers.index(name)]

    # parser is wired to resolve images from the paired ZIP
    assert parser.zip_file_path == "Project1.zip"
    # XML issue sections are preferred over CSV values
    assert value("title") == "SQL Injection"
    assert value("severity") == "High"
    # status falls back to the CSV value and is normalized
    assert value("status") == "Closed"
    assert value("description") == "xml desc"
    # report-level fallbacks
    assert value("client_name") == "Acme"
    assert value("report_name") == "Example Report"
    # asset name falls back to the first useful node label
    assert value("asset_name") == "example.com"
    # generic tag is applied
    assert value("tags") == "dradis_example"


def test_create_temp_data_csv_dradis_example_adds_dynamic_appendix_headers():
    loaded = _make_loaded_dradis()
    parser = CSVParser(header_mapping=mappings.dradis_example_template_mapping)

    temp_csv = mappings.create_temp_data_csv_dradis_example(loaded, parser)
    headers = temp_csv[0]

    assert "Appendix: Methodology" in headers
    assert parser.csv_headers_mapping["Appendix: Methodology"]["mapping_key"] == "report_narrative"
    assert temp_csv[1][headers.index("Appendix: Methodology")] == "appendix body"


def test_dradis_general_proprietary_mapping_is_absent():
    assert not hasattr(mappings, "DRADIS_GENERAL")
    assert not hasattr(mappings, "create_temp_data_csv_dradis_general")
    assert "dradis_general" not in [map_type.value for map_type in mappings.MapType]
