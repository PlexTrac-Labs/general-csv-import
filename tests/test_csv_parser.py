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
    assert parser.enable_rich_text_processing is False


def test_rich_text_processing_is_disabled_by_default():
    parser = CSVParser()

    value = "*should stay textile*"
    assert parser.format_rich_text_value(value, "description") == value


def test_rich_text_processing_can_be_enabled_for_dradis_values():
    parser = CSVParser(enable_rich_text_processing=True)

    result = parser.format_rich_text_value("*bold*", "description")

    # textile converts emphasis to HTML when enabled
    assert "<strong>bold</strong>" in result


def test_dradis_placeholder_angle_brackets_are_escaped_in_narratives():
    parser = CSVParser(enable_rich_text_processing=True)

    result = parser.format_rich_text_value("Contains <dradis.placeholder> token", "Executive Summary")

    assert "<dradis.placeholder>" not in result
    assert "dradis.placeholder" in result


def test_add_image_returns_missing_placeholder_without_zip():
    parser = CSVParser(enable_rich_text_processing=True)

    marker = "!/pro/projects/1/nodes/2/attachments/login.png!"
    result = parser.add_image(marker, "description")

    assert "Missing image for tag" in result
    assert parser.report_media == {}


def test_add_image_extracts_zip_image_bytes_into_report_media(tmp_path):
    parser = CSVParser(enable_rich_text_processing=True)
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    marker = "!/pro/projects/1/nodes/2/attachments/login.png!"
    result = parser.add_image(marker, "description")

    assert result.startswith('<img src="/api/v1/uploads/')
    assert len(parser.report_media) == 1
    media_entry = next(iter(parser.report_media.values()))
    assert "data" in media_entry


def test_add_image_ignores_display_metadata_when_matching_images(tmp_path):
    parser = CSVParser(enable_rich_text_processing=True)
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    value = (
        "!{width:95.0%}/pro/projects/1/nodes/2/attachments/login.png! and "
        "!{height:50%}/pro/projects/1/nodes/2/attachments/login.png!"
    )
    parser.add_image(value, "description")

    # both markers point at the same image despite different metadata
    assert len(parser.report_media) == 1


def test_add_image_caption_becomes_figure_with_figcaption(tmp_path):
    parser = CSVParser(enable_rich_text_processing=True)
    parser.zip_file_path = _make_zip_with_image(tmp_path, "2", "login.png")

    marker = "!/pro/projects/1/nodes/2/attachments/login.png(The login page)!"
    result = parser.add_image(marker, "description")

    assert '<figure class="image">' in result
    assert "<figcaption>The login page</figcaption>" in result


def test_add_image_blank_caption_uses_plain_img_tag(tmp_path):
    parser = CSVParser(enable_rich_text_processing=True)
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
