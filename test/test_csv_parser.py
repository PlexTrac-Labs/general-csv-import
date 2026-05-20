from csv_parser import CSVParser


def test_csv_parser_accepts_injected_header_mapping_as_deep_copy():
    mapping = {
        "Title": {
            "header": "Title",
            "mapping_key": "finding_title",
            "col_index": None,
        }
    }

    parser = CSVParser(header_mapping=mapping)
    parser.csv_headers_mapping["Title"]["col_index"] = 3

    assert parser.get_csv_headers() == ["Title"]
    assert parser.get_index_from_header("Title") == 3
    assert parser.get_mapping_key_from_header("Title") == "finding_title"
    assert mapping["Title"]["col_index"] is None


def test_csv_parser_uses_template_mapping_when_no_mapping_is_injected():
    parser = CSVParser()

    assert parser.csv_headers_mapping == CSVParser.csv_headers_mapping_template
    assert parser.csv_headers_mapping is not CSVParser.csv_headers_mapping_template


def test_finding_mappings_have_merge_metadata():
    parser = CSVParser()

    finding_mappings = {
        key: mapping
        for key, mapping in parser.data_mapping.items()
        if mapping["object_type"] == "FINDING"
    }

    assert finding_mappings["finding_description"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_recommendations"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_references"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_multi_tag"]["merge_type"] == "LIST"
    assert finding_mappings["finding_severity"]["merge_type"] == "SCALAR"
    assert all("merge_type" in mapping for mapping in finding_mappings.values())
    assert all("merge_override" in mapping for mapping in finding_mappings.values())


def test_finding_last_updated_mapping_is_available():
    parser = CSVParser()

    mapping = parser.data_mapping["finding_last_updated_at"]

    assert mapping["object_type"] == "FINDING"
    assert mapping["data_type"] == "DETAIL"
    assert mapping["validation_type"] == "DATE_EPOCH"
    assert mapping["path"] == ["last_update"]
    assert mapping["merge_type"] == "SCALAR"
