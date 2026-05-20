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


def test_user_defined_finding_merge_concatenates_rich_text_and_dedupes_lists():
    parser = CSVParser()
    parser.set_finding_merge_strategy("user_defined_fields")

    report_sid = "report-1"
    first_sid = "finding-1"
    second_sid = "finding-2"
    parser.reports = {report_sid: {"sid": report_sid, "name": "Report", "findings": [first_sid, second_sid]}}
    parser.assets = {}
    parser.findings = {
        first_sid: {
            "sid": first_sid,
            "report_sid": report_sid,
            "title": "Duplicate Finding",
            "severity": "High",
            "status": "Open",
            "description": "First description",
            "recommendations": "Fix it",
            "references": "Ref A",
            "tags": ["one"],
            "fields": {},
            "assets": [],
            "affected_asset_sid": {},
            "dup_num": 1,
        },
        second_sid: {
            "sid": second_sid,
            "report_sid": report_sid,
            "title": "Duplicate Finding",
            "severity": "High",
            "status": "Open",
            "description": "Second description",
            "recommendations": "Fix it",
            "references": "Ref B",
            "tags": ["one", "two"],
            "fields": {},
            "assets": [],
            "affected_asset_sid": {},
            "dup_num": 2,
        },
    }

    parser.handle_finding_dup_names()

    assert list(parser.findings) == [first_sid]
    merged = parser.findings[first_sid]
    assert merged["title"] == "Duplicate Finding"
    assert merged["description"] == "First description\nSecond description"
    assert merged["recommendations"] == "Fix it"
    assert merged["references"] == "Ref A\nRef B"
    assert merged["tags"] == ["one", "two"]
    assert parser.reports[report_sid]["findings"] == [first_sid]
    assert "dup_num" not in merged


def test_all_fields_strategy_does_not_merge_different_rich_text():
    parser = CSVParser()
    parser.set_finding_merge_strategy("all_fields")

    report_sid = "report-1"
    first_sid = "finding-1"
    second_sid = "finding-2"
    parser.reports = {report_sid: {"sid": report_sid, "name": "Report", "findings": [first_sid, second_sid]}}
    parser.assets = {}
    parser.findings = {
        first_sid: {
            "sid": first_sid,
            "report_sid": report_sid,
            "title": "Duplicate Finding",
            "severity": "High",
            "status": "Open",
            "description": "First description",
            "recommendations": "Fix it",
            "references": "Ref A",
            "tags": [],
            "fields": {},
            "assets": [],
            "affected_asset_sid": {},
            "dup_num": 1,
        },
        second_sid: {
            "sid": second_sid,
            "report_sid": report_sid,
            "title": "Duplicate Finding",
            "severity": "High",
            "status": "Open",
            "description": "Second description",
            "recommendations": "Fix it",
            "references": "Ref A",
            "tags": [],
            "fields": {},
            "assets": [],
            "affected_asset_sid": {},
            "dup_num": 2,
        },
    }

    parser.handle_finding_dup_names()

    assert len(parser.findings) == 2
    assert parser.findings[first_sid]["title"] == "Duplicate Finding"
    assert parser.findings[second_sid]["title"] == "Duplicate Finding (2)"


def test_add_asset_to_finding_merges_existing_affected_asset_fields():
    parser = CSVParser()
    parser.asset_merge_strategy = "user_defined_fields"
    finding_sid = "finding-1"
    first_asset_sid = "asset-1"
    second_asset_sid = "asset-2"
    affected_fields_sid = "affected-2"
    parser.assets = {
        first_asset_sid: {"is_multi": False},
        second_asset_sid: {"is_multi": False},
    }
    parser.findings = {
        finding_sid: {"affected_asset_sid": affected_fields_sid}
    }
    parser.affected_assets = {
        affected_fields_sid: {
            "status": "Closed",
            "ports": {443: {"number": "443"}},
            "vulnerableParameters": ["param2"],
            "notes": "second note",
        }
    }
    finding = {
        "affected_assets": {
            "asset-original": {
                "id": "asset-original",
                "status": "Open",
                "ports": {80: {"number": "80"}},
                "vulnerableParameters": ["param1"],
                "notes": "first note",
            }
        }
    }
    new_asset = {
        "id": "asset-original",
        "ports": {},
        "vulnerableParameters": [],
    }

    result = parser.add_asset_to_finding(finding, new_asset, finding_sid, second_asset_sid)

    affected_asset = result["affected_assets"]["asset-original"]
    assert affected_asset["status"] == "Closed"
    assert affected_asset["ports"] == {80: {"number": "80"}, 443: {"number": "443"}}
    assert sorted(affected_asset["vulnerableParameters"]) == ["param1", "param2"]
    assert affected_asset["notes"] == "first note\nsecond note"


def test_affected_asset_evidence_mapping_adds_evidence_object():
    parser = CSVParser(
        header_mapping={
            "Evidence Column": {
                "header": "Evidence Column",
                "mapping_key": "affected_asset_evidence",
                "col_index": 0,
            }
        }
    )
    affected_asset = {"evidence": []}

    parser.add_data_to_object(affected_asset, "AFFECTED_ASSET", ["proof text"])

    evidence = affected_asset["evidence"][0]
    assert evidence["caption"] == "Evidence Column"
    assert evidence["code"] == "proof text"
    assert evidence["type"] == "CodeSample"
    assert evidence["assets"] == []


def test_save_data_as_ptrac_can_return_ptrac_jsons_without_writing_files():
    parser = CSVParser()
    client_sid = "client-1"
    report_sid = "report-1"
    finding_sid = "finding-1"
    parser.doc_version = "2.0.0"
    parser.clients = {
        client_sid: {
            "sid": client_sid,
            "name": "Client",
            "tags": [],
            "custom_field": [],
            "description": "",
            "assets": [],
            "reports": [report_sid],
        }
    }
    parser.reports = {
        report_sid: {
            "sid": report_sid,
            "client_sid": client_sid,
            "name": "Report",
            "status": "Published",
            "tags": [],
            "custom_field": [],
            "start_date": None,
            "end_date": None,
            "exec_summary": {"custom_fields": []},
            "findings": [finding_sid],
        }
    }
    parser.findings = {
        finding_sid: {
            "sid": finding_sid,
            "client_sid": client_sid,
            "report_sid": report_sid,
            "affected_asset_sid": None,
            "title": "Finding",
            "severity": "High",
            "status": "Open",
            "description": "Description",
            "recommendations": "Fix",
            "references": "",
            "fields": {},
            "risk_score": {"CVSS3_1": {"overall": 0, "vector": ""}},
            "common_identifiers": {"CVE": [], "CWE": []},
            "tags": [],
            "affected_assets": {},
            "assets": [],
        }
    }

    ptracs = parser.save_data_as_ptrac(return_ptrac_jsons=True)

    assert len(ptracs) == 1
    assert ptracs[0]["client_info"]["name"] == "Client"
    assert ptracs[0]["report_info"]["name"] == "Report"
    assert ptracs[0]["flaws_array"][0]["title"] == "Finding"
    assert ptracs[0]["flaws_array"][0]["last_update"] == parser.parser_time_milliseconds


def test_parser_initializes_object_lookup_maps():
    parser = CSVParser()

    assert parser.client_lookup == {}
    assert parser.report_lookup == {}
    assert parser.finding_lookup == {}
    assert parser.asset_lookup == {}
    assert parser.evidence_lookup == {}
