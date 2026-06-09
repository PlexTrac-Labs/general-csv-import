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


def _make_loaded_dradis_zip():
    return LoadedDradisData(
        file_path="Project1.zip",
        zip_file_path="Project1.zip",
        nodes=[
            {"id": "1", "label": "Report content", "properties": {"dradis.clientformal": "Acme Formal", "dradis.application": "Web App"}, "raw": {}},
            {
                "id": "2",
                "label": "\\url{https://example.com/}",
                "properties": {},
                "raw": {
                    "evidence": {
                        "evidence": {
                            "id": "100",
                            "issue-id": "10",
                            "content": "#[Vulnerable Target: IPorUrl]#\n\"$\":https://example.com/login\n\n#[Port]#\n443\n\n#[Protocol]#\ntcp",
                        }
                    }
                },
            },
        ],
        issues=[
            {
                "id": "10",
                "title": "Graph Finding",
                "sections": {
                    "title": "Graph Finding",
                    "rating": "Medium",
                    "details": "Graph details",
                    "remediation": "Fix it",
                    "references": "https://ref.example",
                    "cvssv3.vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
                },
                "raw": {"state": "ready_for_review"},
            },
            {
                "id": "11",
                "title": "No Evidence Finding",
                "sections": {"title": "No Evidence Finding", "rating": "Low", "details": "No evidence details"},
                "raw": {"state": "closed"},
            },
        ],
        content_blocks=[
            {"group": "Introduction", "title": "", "content": "intro", "sections": {"description": "Intro text"}},
            {"group": "ExecutiveSummary", "title": "", "content": "exec", "sections": {"description": "Exec text"}},
        ],
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


def test_resolve_returns_example_dradis_csv_spec():
    spec = mappings.resolve(mappings.MapType.EXAMPLE_DRADIS_CSV.value)

    assert spec.mapping is mappings.example_dradis_csv_template_mapping
    assert spec.load_data_function is mappings.load_data_file_example_dradis_csv
    assert spec.verify_function is mappings.verify_example_dradis_csv_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_example_dradis_csv
    assert spec.find_input_files_function is mappings.find_input_files_dradis_pair
    assert spec.default_finding_merge_strategy is None
    assert spec.enable_rich_text_processing is True


def test_resolve_returns_example_dradis_zip_spec():
    spec = mappings.resolve(mappings.MapType.EXAMPLE_DRADIS_ZIP.value)

    assert spec.mapping is mappings.example_dradis_zip_template_mapping
    assert spec.load_data_function is mappings.load_data_file_example_dradis_zip
    assert spec.verify_function is mappings.verify_example_dradis_zip_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_example_dradis_zip
    assert spec.find_input_files_function is mappings.find_input_files_dradis_zip
    assert spec.default_finding_merge_strategy == "user_defined_fields"
    assert spec.enable_rich_text_processing is True


def test_verify_example_dradis_csv_payload_requires_headers_rows_nodes_and_blocks():
    valid = _make_loaded_dradis()
    assert mappings.verify_example_dradis_csv_payload(valid) is True

    no_headers = _make_loaded_dradis()
    no_headers.headers = []
    assert mappings.verify_example_dradis_csv_payload(no_headers) is False

    no_rows = _make_loaded_dradis()
    no_rows.row_dicts = []
    assert mappings.verify_example_dradis_csv_payload(no_rows) is False

    no_nodes = _make_loaded_dradis()
    no_nodes.nodes = []
    assert mappings.verify_example_dradis_csv_payload(no_nodes) is False

    no_blocks = _make_loaded_dradis()
    no_blocks.content_blocks = []
    assert mappings.verify_example_dradis_csv_payload(no_blocks) is False


def test_create_temp_data_csv_example_dradis_csv_builds_generic_fields():
    loaded = _make_loaded_dradis()
    parser = CSVParser(header_mapping=mappings.example_dradis_csv_template_mapping)

    temp_csv = mappings.create_temp_data_csv_example_dradis_csv(loaded, parser)

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
    assert value("tags") == "example_dradis_csv"


def test_create_temp_data_csv_example_dradis_csv_adds_dynamic_appendix_headers():
    loaded = _make_loaded_dradis()
    parser = CSVParser(header_mapping=mappings.example_dradis_csv_template_mapping)

    temp_csv = mappings.create_temp_data_csv_example_dradis_csv(loaded, parser)
    headers = temp_csv[0]

    assert "Appendix: Methodology" in headers
    assert parser.csv_headers_mapping["Appendix: Methodology"]["mapping_key"] == "report_narrative"
    assert temp_csv[1][headers.index("Appendix: Methodology")] == "appendix body"


def test_verify_example_dradis_zip_payload_requires_nodes_and_issues():
    valid = _make_loaded_dradis_zip()
    assert mappings.verify_example_dradis_zip_payload(valid) is True

    no_nodes = _make_loaded_dradis_zip()
    no_nodes.nodes = []
    assert mappings.verify_example_dradis_zip_payload(no_nodes) is False

    no_issues = _make_loaded_dradis_zip()
    no_issues.issues = []
    assert mappings.verify_example_dradis_zip_payload(no_issues) is False


def test_create_temp_data_csv_example_dradis_zip_builds_graph_rows():
    loaded = _make_loaded_dradis_zip()
    parser = CSVParser(header_mapping=mappings.example_dradis_zip_template_mapping)

    temp_csv = mappings.create_temp_data_csv_example_dradis_zip(loaded, parser)

    assert parser.zip_file_path == "Project1.zip"
    assert len(temp_csv) == 3
    evidence_row = dict(zip(temp_csv[0], temp_csv[1]))
    no_evidence_row = dict(zip(temp_csv[0], temp_csv[2]))

    assert evidence_row["client_name"] == "Acme Formal"
    assert evidence_row["report_name"] == "Web App"
    assert evidence_row["report_tags"] == "example_dradis_zip"
    assert evidence_row["Introduction"] == "Intro text"
    assert evidence_row["Executive Summary"] == "Exec text"
    assert evidence_row["title"] == "Graph Finding"
    assert evidence_row["severity"] == "Medium"
    assert evidence_row["status"] == "Open"
    assert evidence_row["description"] == "Graph details"
    assert evidence_row["recommendations"] == "Fix it"
    assert evidence_row["references"] == "https://ref.example"
    assert evidence_row["cvss_vector"] == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N"
    assert evidence_row["asset_name"] == "https://example.com/"
    assert evidence_row["affected_asset_location_url"] == "https://example.com/login"
    assert evidence_row["affected_asset_port_number"] == "443"
    assert evidence_row["affected_asset_port_protocol"] == "tcp"
    assert evidence_row["tags"] == "example_dradis_zip"

    assert no_evidence_row["title"] == "No Evidence Finding"
    assert no_evidence_row["status"] == "Closed"
    assert no_evidence_row["asset_name"] == ""
    assert no_evidence_row["affected_asset_location_url"] == ""


def test_dradis_general_proprietary_mapping_is_absent():
    assert not hasattr(mappings, "DRADIS_GENERAL")
    assert not hasattr(mappings, "create_temp_data_csv_dradis_general")
    assert "dradis_general" not in [map_type.value for map_type in mappings.MapType]
