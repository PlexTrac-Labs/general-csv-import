import zipfile

from csv_parser import CSVParser
import utils.general_utils as utils


def _make_zip_with_image(folder, node_id, file_name, image_bytes=b"\x89PNGfakedata"):
    zip_path = folder / "dradis.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        zip_ref.writestr(f"{node_id}/{file_name}", image_bytes)
    return str(zip_path)


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


def test_csv_parser_does_not_add_finding_merge_metadata_at_runtime():
    assert not hasattr(CSVParser, "_add_finding_merge_metadata")


def test_csv_parser_does_not_expose_import_data_method():
    assert not hasattr(CSVParser, "import_data")


def test_finding_mappings_have_merge_metadata_on_static_data_mapping():
    finding_mappings = {
        key: mapping
        for key, mapping in CSVParser.data_mapping.items()
        if mapping["object_type"] == "FINDING"
    }

    assert finding_mappings["finding_description"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_recommendations"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_references"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_custom_field"]["merge_type"] == "RICH_TEXT"
    assert finding_mappings["finding_tag"]["merge_type"] == "LIST"
    assert finding_mappings["finding_multi_tag"]["merge_type"] == "LIST"
    assert finding_mappings["finding_cve"]["merge_type"] == "LIST"
    assert finding_mappings["finding_cwe"]["merge_type"] == "LIST"
    assert finding_mappings["finding_severity"]["merge_type"] == "SCALAR"
    assert all("merge_type" in mapping for mapping in finding_mappings.values())
    assert all("merge_override" in mapping for mapping in finding_mappings.values())
    assert all(mapping["merge_override"] is None for mapping in finding_mappings.values())


def test_parser_instance_inherits_static_finding_merge_metadata():
    parser = CSVParser()

    assert parser.data_mapping["finding_description"]["merge_type"] == "RICH_TEXT"
    assert parser.data_mapping["finding_severity"]["merge_type"] == "SCALAR"


def test_finding_last_updated_mapping_is_available():
    mapping = CSVParser.data_mapping["finding_last_updated_at"]

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
    # affected_asset_sid is now a per-asset dict {asset_sid: affected_fields_sid}
    parser.findings = {
        finding_sid: {"affected_asset_sid": {second_asset_sid: affected_fields_sid}}
    }
    parser.affected_assets = {
        affected_fields_sid: {
            "status": "Closed",
            "ports": {443: {"number": "443"}},
            "vulnerableParameters": ["param2"],
            "evidence": [],
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


def _status_sync_parser(finding_status_mapped, asset_status_mapped, override=False):
    """Build a parser whose header mapping reflects which status fields are mapped."""
    parser = CSVParser()
    parser.override_finding_status_from_assets = override
    header_mapping = {}
    if finding_status_mapped:
        header_mapping["FS"] = {"header": "FS", "mapping_key": "finding_status", "col_index": 0}
    if asset_status_mapped:
        header_mapping["AS"] = {"header": "AS", "mapping_key": "affected_asset_status", "col_index": 1}
    parser.csv_headers_mapping = header_mapping
    return parser


def _run_status_sync(parser, finding_status, asset_statuses):
    """Set up one finding with the given raw statuses, sync, and return resolved values."""
    parser.findings = {"f1": {"status": finding_status, "affected_asset_sid": {}}}
    parser.affected_assets = {}
    for i, status in enumerate(asset_statuses):
        record_sid = f"r{i}"
        parser.findings["f1"]["affected_asset_sid"][f"a{i}"] = record_sid
        parser.affected_assets[record_sid] = {"status": status}
    parser.sync_statuses()
    resolved_assets = [
        parser.affected_assets[sid]["status"]
        for sid in parser.findings["f1"]["affected_asset_sid"].values()
    ]
    return parser.findings["f1"]["status"], resolved_assets


def test_most_open_status_orders_open_over_closed():
    parser = CSVParser()
    assert parser._most_open_status(["Closed", "Open"]) == "Open"
    assert parser._most_open_status(["Closed", "In Process"]) == "In Process"
    assert parser._most_open_status(["Closed", "Closed"]) == "Closed"
    assert parser._most_open_status([None, "bogus"]) is None


def test_sync_statuses_neither_mapped_defaults_open():
    parser = _status_sync_parser(finding_status_mapped=False, asset_status_mapped=False)
    finding_status, asset_statuses = _run_status_sync(parser, None, [None])
    assert finding_status == "Open"
    assert asset_statuses == ["Open"]


def test_sync_statuses_finding_mapped_only_fills_assets_from_finding():
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=False)
    finding_status, asset_statuses = _run_status_sync(parser, "Closed", [None, None])
    assert finding_status == "Closed"
    assert asset_statuses == ["Closed", "Closed"]


def test_sync_statuses_asset_mapped_only_rolls_up_to_finding():
    parser = _status_sync_parser(finding_status_mapped=False, asset_status_mapped=True)
    finding_status, asset_statuses = _run_status_sync(parser, None, ["Closed", "In Process"])
    assert finding_status == "In Process"
    assert asset_statuses == ["Closed", "In Process"]


def test_sync_statuses_both_mapped_source_is_truth_keeps_out_of_sync():
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True)
    finding_status, asset_statuses = _run_status_sync(parser, "Open", ["Closed"])
    assert finding_status == "Open"
    assert asset_statuses == ["Closed"]


def test_sync_statuses_both_mapped_fills_missing_per_row_value():
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True)
    # finding provided, one asset missing -> missing asset adopts finding status
    finding_status, asset_statuses = _run_status_sync(parser, "Closed", [None, "Closed"])
    assert finding_status == "Closed"
    assert asset_statuses == ["Closed", "Closed"]
    # finding missing, assets provided -> finding derived from rollup
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True)
    finding_status, asset_statuses = _run_status_sync(parser, None, ["Closed"])
    assert finding_status == "Closed"


def test_sync_statuses_override_derives_finding_from_asset_rollup():
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True, override=True)
    finding_status, asset_statuses = _run_status_sync(parser, "Open", ["Closed"])
    assert finding_status == "Closed"
    assert asset_statuses == ["Closed"]

    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True, override=True)
    finding_status, _ = _run_status_sync(parser, "Closed", ["Closed", "Open"])
    assert finding_status == "Open"


def test_sync_statuses_closed_at_forces_finding_closed():
    # a close date is authoritative: finding is Closed and assets follow, even though the
    # source finding status and asset statuses say Open
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True)
    parser.findings = {
        "f1": {"status": "Open", "closedAt": 1700000000000, "affected_asset_sid": {"a0": "r0"}}
    }
    parser.affected_assets = {"r0": {"status": None}}
    parser.sync_statuses()
    assert parser.findings["f1"]["status"] == "Closed"
    assert parser.affected_assets["r0"]["status"] == "Closed"


def test_sync_statuses_override_lets_assets_unclose_finding_with_close_date():
    # corner case: override ON, all three present (close date + finding status + asset status).
    # The open affected asset "uncloses" the finding, and the close date is ignored.
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True, override=True)
    parser.findings = {
        "f1": {"status": "Closed", "closedAt": 1700000000000, "affected_asset_sid": {"a0": "r0"}}
    }
    parser.affected_assets = {"r0": {"status": "Open"}}
    parser.sync_statuses()
    assert parser.findings["f1"]["status"] == "Open"
    assert parser.affected_assets["r0"]["status"] == "Open"


def test_sync_statuses_override_off_keeps_close_date_finding_closed():
    # same inputs but override OFF: source is truth, finding stays Closed even though the
    # affected asset is Open (the two may remain out of sync)
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True, override=False)
    parser.findings = {
        "f1": {"status": "Open", "closedAt": 1700000000000, "affected_asset_sid": {"a0": "r0"}}
    }
    parser.affected_assets = {"r0": {"status": "Open"}}
    parser.sync_statuses()
    assert parser.findings["f1"]["status"] == "Closed"
    assert parser.affected_assets["r0"]["status"] == "Open"


def test_sync_statuses_stamps_close_date_on_closed_finding():
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=False)
    parser.findings = {"f1": {"status": "Closed", "affected_asset_sid": {}}}
    parser.affected_assets = {}
    parser.sync_statuses()
    assert parser.findings["f1"]["closedAt"] == parser.parser_time_milliseconds


def test_sync_statuses_drops_close_date_when_not_closed():
    # override lets an open asset unclose the finding; the stale close date is dropped on
    # the parsed object itself (not just at generation)
    parser = _status_sync_parser(finding_status_mapped=True, asset_status_mapped=True, override=True)
    parser.findings = {
        "f1": {"status": "Closed", "closedAt": 1700000000000, "affected_asset_sid": {"a0": "r0"}}
    }
    parser.affected_assets = {"r0": {"status": "Open"}}
    parser.sync_statuses()
    assert parser.findings["f1"]["status"] == "Open"
    assert parser.findings["f1"]["closedAt"] is None


def test_parsed_finding_objects_are_status_consistent_without_generation():
    mapping = {
        "Title": {"header": "Title", "mapping_key": "finding_title", "col_index": 0},
        "FStatus": {"header": "FStatus", "mapping_key": "finding_status", "col_index": 1},
        "ClosedAt": {"header": "ClosedAt", "mapping_key": "finding_closed_at", "col_index": 2},
    }
    parser = CSVParser(header_mapping=mapping)
    parser.doc_version = "3.1.0"
    for header in mapping.values():
        header["matched"] = True
    # row 1: Closed with no date -> stamped; row 2: Open with no date -> closedAt is None
    parser.csv_data = [["Vuln A", "Closed", ""], ["Vuln B", "Open", ""]]
    assert parser.parse_data()
    findings_by_title = {f["title"]: f for f in parser.findings.values()}
    assert findings_by_title["Vuln A"]["status"] == "Closed"
    assert findings_by_title["Vuln A"]["closedAt"] == parser.parser_time_milliseconds
    assert findings_by_title["Vuln B"]["status"] == "Open"
    assert findings_by_title["Vuln B"]["closedAt"] is None


def test_generate_ptrac_override_drops_stale_close_date_when_unclosed():
    mapping = {
        "Title": {"header": "Title", "mapping_key": "finding_title", "col_index": 0},
        "FStatus": {"header": "FStatus", "mapping_key": "finding_status", "col_index": 1},
        "AStatus": {"header": "AStatus", "mapping_key": "affected_asset_status", "col_index": 2},
        "Asset": {"header": "Asset", "mapping_key": "asset_name", "col_index": 3},
        "ClosedAt": {"header": "ClosedAt", "mapping_key": "finding_closed_at", "col_index": 4},
    }
    parser = CSVParser(header_mapping=mapping)
    parser.doc_version = "3.1.0"
    parser.override_finding_status_from_assets = True
    for header in mapping.values():
        header["matched"] = True
    parser.csv_data = [["Vuln A", "Closed", "Open", "host1", "01/15/2024"]]
    assert parser.parse_data()
    flaw = parser.generate_ptrac_json_data()[0]["flaws_array"][0]
    assert flaw["status"] == "Open"
    assert flaw["closedAt"] is None


def test_generate_ptrac_sets_now_timestamp_for_closed_finding_without_close_date():
    mapping = {
        "Title": {"header": "Title", "mapping_key": "finding_title", "col_index": 0},
        "FStatus": {"header": "FStatus", "mapping_key": "finding_status", "col_index": 1},
    }
    parser = CSVParser(header_mapping=mapping)
    parser.doc_version = "3.1.0"
    for header in mapping.values():
        header["matched"] = True
    parser.csv_data = [["Vuln A", "Closed"]]
    assert parser.parse_data()
    ptracs = parser.generate_ptrac_json_data()
    flaw = ptracs[0]["flaws_array"][0]
    assert flaw["status"] == "Closed"
    # no close date was mapped, so it is stamped with the parser run timestamp
    assert flaw["closedAt"] == parser.parser_time_milliseconds


def test_generate_ptrac_preserves_mapped_close_date_and_forces_closed():
    mapping = {
        "Title": {"header": "Title", "mapping_key": "finding_title", "col_index": 0},
        "FStatus": {"header": "FStatus", "mapping_key": "finding_status", "col_index": 1},
        "ClosedAt": {"header": "ClosedAt", "mapping_key": "finding_closed_at", "col_index": 2},
    }
    parser = CSVParser(header_mapping=mapping)
    parser.doc_version = "3.1.0"
    for header in mapping.values():
        header["matched"] = True
    # source says Open, but a close date is present -> finding must be Closed and keep the date
    parser.csv_data = [["Vuln A", "Open", "01/15/2024"]]
    assert parser.parse_data()
    ptracs = parser.generate_ptrac_json_data()
    flaw = ptracs[0]["flaws_array"][0]
    assert flaw["status"] == "Closed"
    assert flaw["closedAt"] is not None
    assert flaw["closedAt"] != parser.parser_time_milliseconds


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


def test_generate_ptrac_json_data_returns_ptrac_schema():
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
            "affected_asset_sid": {},
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

    ptracs = parser.generate_ptrac_json_data()

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


def test_parser_initializes_report_media_state():
    parser = CSVParser()

    assert parser.report_media == {}
    assert parser.report_media_lookup == {}
    assert parser.zip_file_path is None
    assert parser.rich_text_source_format is None


def test_rich_text_processing_is_disabled_by_default():
    parser = CSVParser()

    value = "*should stay textile*"
    assert parser.format_rich_text_value(value, "description") == value


def test_rich_text_processing_can_be_enabled_for_dradis_values():
    parser = CSVParser(rich_text_source_format="textile")

    result = parser.format_rich_text_value("*bold*", "description")

    # textile converts emphasis to HTML when enabled
    assert "<strong>bold</strong>" in result


def test_dradis_placeholder_angle_brackets_are_escaped_in_narratives():
    parser = CSVParser(rich_text_source_format="textile")

    result = parser.format_rich_text_value("Contains <dradis.placeholder> token", "Executive Summary")

    assert "<dradis.placeholder>" not in result
    assert "dradis.placeholder" in result


def test_add_image_returns_missing_placeholder_without_zip():
    parser = CSVParser(rich_text_source_format="textile")

    marker = "!/pro/projects/1/nodes/2/attachments/login.png!"
    result = parser.add_image(marker, "description")

    assert "Missing image for tag" in result
    assert parser.report_media == {}


def test_add_image_extracts_zip_image_bytes_into_report_media(tmp_path):
    parser = CSVParser(rich_text_source_format="textile")
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    marker = "!/pro/projects/1/nodes/2/attachments/login.png!"
    result = parser.add_image(marker, "description")

    assert result.startswith('<img src="/api/v1/uploads/')
    assert len(parser.report_media) == 1
    media_entry = next(iter(parser.report_media.values()))
    assert "data" in media_entry


def test_add_image_ignores_display_metadata_when_matching_images(tmp_path):
    parser = CSVParser(rich_text_source_format="textile")
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    value = (
        "!{width:95.0%}/pro/projects/1/nodes/2/attachments/login.png! and "
        "!{height:50%}/pro/projects/1/nodes/2/attachments/login.png!"
    )
    parser.add_image(value, "description")

    # both markers point at the same image despite different metadata
    assert len(parser.report_media) == 1


def test_add_image_caption_becomes_figure_with_figcaption(tmp_path):
    parser = CSVParser(rich_text_source_format="textile")
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    marker = "!/pro/projects/1/nodes/2/attachments/login.png(The login page)!"
    result = parser.add_image(marker, "description")

    assert '<figure class="image">' in result
    assert "<figcaption>The login page</figcaption>" in result


def test_add_image_blank_caption_uses_plain_img_tag(tmp_path):
    parser = CSVParser(rich_text_source_format="textile")
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    marker = "!/pro/projects/1/nodes/2/attachments/login.png!"
    result = parser.add_image(marker, "description")

    assert result.startswith('<img src="/api/v1/uploads/')
    assert "<figure" not in result


def test_generated_ptrac_contains_report_media_summary():
    parser = CSVParser()
    parser.doc_version = "2.0.0"
    parser.report_media = {"abc.png": {"data": "ZmFrZQ=="}}
    client_sid = "client-1"
    report_sid = "report-1"
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
            "findings": [],
        }
    }

    ptracs = parser.generate_ptrac_json_data()

    assert "ReportMedia" in ptracs[0]["summary"]
    assert ptracs[0]["summary"]["ReportMedia"] == {"abc.png": {"data": "ZmFrZQ=="}}


# ---- CVSS validation type routing -------------------------------------------

def _validate(mapping_key: str, value: str):
    """Run validate_value for a single mapping key through a throwaway parser."""
    parser = CSVParser()
    mapping = parser.data_mapping[mapping_key]
    return parser.validate_value(mapping["id"], mapping, value)


def test_cvss_vector_accepts_3x_vectors():
    assert _validate("finding_cvss3_1_vector", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert _validate("finding_cvss3_1_vector", "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert _validate("finding_cvss3_1_vector", "cvss:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    # Bare metric string also accepted
    assert _validate("finding_cvss3_1_vector", "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


def test_cvss_vector_rejects_40_and_garbage():
    # 4.0 vectors must go to finding_cvss4_vector, not finding_cvss3_1_vector
    assert _validate("finding_cvss3_1_vector", "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N") is None
    assert _validate("finding_cvss3_1_vector", "not-a-vector") is None


def test_cvss4_vector_accepts_40_and_normalises_prefix():
    full = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
    assert _validate("finding_cvss4_vector", full) == full
    # Lowercase prefix normalised
    lower = "cvss:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
    assert _validate("finding_cvss4_vector", lower) == full


def test_cvss4_vector_rejects_3x_and_garbage():
    assert _validate("finding_cvss4_vector", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is None
    assert _validate("finding_cvss4_vector", "not-a-vector") is None


def test_finding_template_includes_cvss4_risk_score_section():
    parser = CSVParser()
    cvss4 = parser.finding_template["risk_score"]["CVSS4"]
    assert "overall" in cvss4
    assert "vector" in cvss4
    assert "cvss4" not in parser.finding_template["fields"]["scores"]


# ---- per-asset affected fields, evidence, parent assets, asset-only rows ----
# End-to-end coverage driving parse_data() -> generate_ptrac_json_data().

def _run_end_to_end(columns, rows, merge_strategy=None):
    """
    Build a parser with an explicit header mapping, parse the rows, and return the generated ptracs.

    :param columns: list of (header, mapping_key) tuples; col_index is assigned by position
    :param rows: list of CSV value-lists (the header row is NOT included)
    :param merge_strategy: optional finding/asset merge strategy
    """
    mapping = {
        header: {"header": header, "mapping_key": mapping_key, "col_index": index}
        for index, (header, mapping_key) in enumerate(columns)
    }
    parser = CSVParser(header_mapping=mapping)
    parser.doc_version = "2.0.0"
    parser.csv_data = [list(row) for row in rows]
    if merge_strategy:
        parser.set_finding_merge_strategy(merge_strategy)
    assert parser.parse_data() is True
    return parser.generate_ptrac_json_data()


def test_per_asset_location_url_survives_finding_merge():
    # Bug B: distinct assets on a merged finding must each keep their own affected-asset detail.
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("URL", "affected_asset_location_url"),
    ]
    rows = [
        ["SQL Injection", "web-1", "http://host/one"],
        ["SQL Injection", "web-2", "http://host/two"],
    ]

    ptracs = _run_end_to_end(columns, rows, merge_strategy="user_defined_fields")

    assert len(ptracs) == 1
    flaws = ptracs[0]["flaws_array"]
    assert len(flaws) == 1  # the two rows merged into one finding
    affected_assets = flaws[0]["affected_assets"]
    assert len(affected_assets) == 2
    urls_by_name = {aa["asset"]: aa["locationUrl"] for aa in affected_assets.values()}
    assert urls_by_name == {"web-1": "http://host/one", "web-2": "http://host/two"}


def test_evidence_is_written_to_ptrac_and_referenced_by_affected_asset():
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("Evidence", "affected_asset_evidence"),
    ]
    rows = [["XSS", "web-1", "proof of concept"]]

    ptracs = _run_end_to_end(columns, rows)

    report_evidence = ptracs[0]["evidence"]
    assert len(report_evidence) == 1
    evidence = report_evidence[0]
    assert evidence["caption"] == "Evidence"
    assert evidence["code"] == "proof of concept"

    affected_assets = ptracs[0]["flaws_array"][0]["affected_assets"]
    assert len(affected_assets) == 1
    affected_asset = next(iter(affected_assets.values()))
    # the affected asset carries only a reference id; the object lives in the report-level array
    assert affected_asset["evidence"] == [evidence["id"]]
    assert evidence["assets"] == [affected_asset["id"]]


def test_evidence_with_shared_caption_and_code_is_deduped():
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("Evidence", "affected_asset_evidence"),
    ]
    rows = [
        ["XSS", "web-1", "identical proof"],
        ["XSS", "web-1", "identical proof"],
    ]

    ptracs = _run_end_to_end(columns, rows, merge_strategy="user_defined_fields")

    flaws = ptracs[0]["flaws_array"]
    assert len(flaws) == 1
    affected_assets = flaws[0]["affected_assets"]
    assert len(affected_assets) == 1  # same asset name -> one affected asset
    affected_asset = next(iter(affected_assets.values()))
    assert len(affected_asset["evidence"]) == 1
    assert len(ptracs[0]["evidence"]) == 1
    assert affected_asset["evidence"] == [ptracs[0]["evidence"][0]["id"]]


def test_referenced_parent_is_materialized_with_real_id_link():
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("Parent", "parent_asset"),
    ]
    rows = [
        ["Finding A", "web-1", "host"],
        ["Finding B", "web-2", "host"],
    ]

    ptracs = _run_end_to_end(columns, rows)

    report_assets = ptracs[0]["summary"]["ReportAssets"]
    assets_by_name = {ra["asset"]: ra for ra in report_assets.values()}
    assert set(assets_by_name) == {"web-1", "web-2", "host"}

    host_id = assets_by_name["host"]["id"]
    assert assets_by_name["host"]["parent_asset"] is None
    assert assets_by_name["web-1"]["parent_asset"] == host_id
    assert assets_by_name["web-2"]["parent_asset"] == host_id
    # the link resolves to a real key in ReportAssets
    assert host_id in report_assets


def test_self_parenting_is_skipped():
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("Parent", "parent_asset"),
    ]
    rows = [["Finding", "host", "host"]]

    ptracs = _run_end_to_end(columns, rows)

    report_assets = ptracs[0]["summary"]["ReportAssets"]
    assert len(report_assets) == 1
    host = next(iter(report_assets.values()))
    assert host["asset"] == "host"
    assert host["parent_asset"] is None


def test_asset_only_row_supplies_detail_to_referenced_parent():
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("Parent", "parent_asset"),
        ("OS", "asset_operating_systems"),
    ]
    rows = [
        ["Finding", "web-1", "host", ""],   # child references parent "host"
        ["", "host", "", "Linux"],          # asset-only row gives "host" its own detail
    ]

    ptracs = _run_end_to_end(columns, rows)

    # the asset-only row must not create a finding
    flaws = ptracs[0]["flaws_array"]
    assert len(flaws) == 1
    assert flaws[0]["title"] == "Finding"

    report_assets = ptracs[0]["summary"]["ReportAssets"]
    assets_by_name = {ra["asset"]: ra for ra in report_assets.values()}
    assert "host" in assets_by_name
    # detail from the asset-only row reached the materialized parent
    assert assets_by_name["host"]["operating_system"] == ["Linux"]


def test_transitive_parent_chain_resolves_and_ptrac_is_json_serializable():
    import json

    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("Parent", "parent_asset"),
    ]
    rows = [
        ["Finding", "child", "parent"],        # child -> parent
        ["", "parent", "grandparent"],         # asset-only row links parent -> grandparent
    ]

    ptracs = _run_end_to_end(columns, rows)
    report_assets = ptracs[0]["summary"]["ReportAssets"]
    assets_by_name = {ra["asset"]: ra for ra in report_assets.values()}

    assert set(assets_by_name) == {"child", "parent", "grandparent"}
    assert assets_by_name["child"]["parent_asset"] == assets_by_name["parent"]["id"]
    assert assets_by_name["parent"]["parent_asset"] == assets_by_name["grandparent"]["id"]
    assert assets_by_name["grandparent"]["parent_asset"] is None

    # every parent_asset id resolves to a real key in ReportAssets
    for ra in report_assets.values():
        if ra["parent_asset"] is not None:
            assert ra["parent_asset"] in report_assets

    # the whole ptrac must be JSON-serializable (no stray UUID objects)
    json.dumps(ptracs[0])


def test_multi_name_assets_generate_with_blank_affected_fields():
    # multi-name assets are never linked in affected_asset_sid; they must hit the blank fallback
    columns = [
        ("Title", "finding_title"),
        ("Assets", "asset_multi_name"),
    ]
    rows = [["Open Port", "a, b, c"]]

    ptracs = _run_end_to_end(columns, rows)

    flaws = ptracs[0]["flaws_array"]
    assert len(flaws) == 1
    affected_assets = flaws[0]["affected_assets"]
    assert sorted(aa["asset"] for aa in affected_assets.values()) == ["a", "b", "c"]
    report_assets = ptracs[0]["summary"]["ReportAssets"]
    assert sorted(ra["asset"] for ra in report_assets.values()) == ["a", "b", "c"]
    assert ptracs[0]["evidence"] == []  # no affected fields -> no evidence


def test_single_asset_with_fields_coexists_with_multi_name_assets():
    columns = [
        ("Title", "finding_title"),
        ("Asset", "asset_name"),
        ("URL", "affected_asset_location_url"),
        ("Multi", "asset_multi_name"),
    ]
    rows = [["Finding", "web-1", "http://host/x", "m1, m2"]]

    ptracs = _run_end_to_end(columns, rows)

    affected_by_name = {aa["asset"]: aa for aa in ptracs[0]["flaws_array"][0]["affected_assets"].values()}
    assert set(affected_by_name) == {"web-1", "m1", "m2"}
    assert affected_by_name["web-1"]["locationUrl"] == "http://host/x"
    # multi-name assets fall back to the blank affected-asset template
    assert affected_by_name["m1"]["locationUrl"] == ""
    assert affected_by_name["m2"]["locationUrl"] == ""
