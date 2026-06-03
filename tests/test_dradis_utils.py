import zipfile

import pytest

import mapping_utils.dradis_utils as dradis


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dradis-export>
  <nodes>
    <node>
      <id>1</id>
      <label>example.com</label>
      <type-id>1</type-id>
      <parent-id></parent-id>
      <properties>{"host": "example.com"}</properties>
    </node>
    <node>
      <id>2</id>
      <label>Report content</label>
      <properties>{"report_title": "Example Report", "client": "Acme", "report_date": "May 8, 2026"}</properties>
    </node>
  </nodes>
  <issues>
    <issue>
      <id>10</id>
      <text>#[Title]#
SQL Injection

#[Rating]#
High

#[Description]#
The application is vulnerable.</text>
    </issue>
  </issues>
  <content-blocks>
    <content-block>
      <id>20</id>
      <block-group>Introduction</block-group>
      <content>#[Description]#
This is the introduction.</content>
    </content-block>
  </content-blocks>
</dradis-export>
"""

EMPTY_CONTAINERS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<dradis-export>
  <nodes></nodes>
  <issues></issues>
  <content-blocks></content-blocks>
</dradis-export>
"""


def _write_pair(folder, basename, csv_text, xml_text):
    csv_path = folder / f"{basename}.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    zip_path = folder / f"{basename}.zip"
    with zipfile.ZipFile(zip_path, "w") as zip_ref:
        zip_ref.writestr("dradis-repository.xml", xml_text)
    return str(csv_path), str(zip_path)


def test_parse_dradis_sections_parses_titles_ratings_and_custom_fields():
    text = "#[Title]#\nSQL Injection\n\n#[Rating]#\nHigh\n\n#[Custom Field]#\nsome value"
    sections = dradis.parse_dradis_sections(text)

    assert sections["title"] == "SQL Injection"
    assert sections["rating"] == "High"
    assert sections["custom_field"] == "some value"


def test_normalize_section_key_converts_spaces_to_underscores():
    assert dradis.normalize_section_key("Proof Of Concept") == "proof_of_concept"


def test_parse_properties_json_handles_invalid_and_valid():
    assert dradis.parse_properties_json("not json") == {}
    assert dradis.parse_properties_json("") == {}
    assert dradis.parse_properties_json('{"a": 1}') == {"a": 1}
    assert dradis.parse_properties_json({"already": "dict"}) == {"already": "dict"}


def test_get_csv_value_chooses_first_non_blank_matching_header():
    row = {"Title": "", "Finding Name": "XSS", "Vulnerability Name": "ignored"}
    assert dradis.get_csv_value(row, ["Title", "Finding Name", "Vulnerability Name"]) == "XSS"
    assert dradis.get_csv_value(row, ["Missing"], default="fallback") == "fallback"


def test_first_value_returns_first_non_blank():
    assert dradis.first_value("", "  ", "real", "other") == "real"
    assert dradis.first_value("", None) == ""


def test_find_paired_zip_returns_same_basename_zip(tmp_path):
    csv_path = tmp_path / "Project1.csv"
    assert dradis.find_paired_zip(str(csv_path)) == str(tmp_path / "Project1.zip")


def test_find_dradis_csv_candidates_only_returns_csv_with_zip_pairs(tmp_path):
    _write_pair(tmp_path, "Paired", "Title\nX\n", SAMPLE_XML)
    (tmp_path / "Unpaired.csv").write_text("Title\nY\n", encoding="utf-8")

    candidates = dradis.find_dradis_csv_candidates(str(tmp_path))

    assert candidates == [str(tmp_path / "Paired.csv")]


def test_load_dradis_pair_normalizes_properties_issues_and_content_blocks(tmp_path):
    csv_path, _ = _write_pair(
        tmp_path, "Report",
        "Title,Severity,Status\nSQL Injection,High,Open\n",
        SAMPLE_XML,
    )

    loaded = dradis.load_dradis_pair(csv_path)

    assert loaded.headers == ["Title", "Severity", "Status"]
    assert loaded.row_dicts[0]["Title"] == "SQL Injection"
    assert loaded.nodes[0]["properties"] == {"host": "example.com"}
    assert loaded.report_properties["report_title"] == "Example Report"
    assert loaded.issues[0]["title"] == "SQL Injection"
    assert loaded.issues[0]["sections"]["rating"] == "High"
    assert loaded.content_blocks[0]["group"] == "Introduction"
    assert loaded.content_blocks[0]["sections"]["description"] == "This is the introduction."


def test_load_dradis_pair_handles_empty_containers_as_empty_lists(tmp_path):
    csv_path, _ = _write_pair(tmp_path, "Empty", "Title\nX\n", EMPTY_CONTAINERS_XML)

    loaded = dradis.load_dradis_pair(csv_path)

    assert loaded.nodes == []
    assert loaded.issues == []
    assert loaded.content_blocks == []


def test_load_dradis_pair_missing_zip_raises(tmp_path):
    csv_path = tmp_path / "NoZip.csv"
    csv_path.write_text("Title\nX\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        dradis.load_dradis_pair(str(csv_path))


def test_find_dradis_image_reference_parses_standard_marker():
    ref = dradis.find_dradis_image_reference("text !/pro/projects/1/nodes/2/attachments/login%20page.png! more")

    assert ref is not None
    assert ref.project_id == "1"
    assert ref.node_id == "2"
    assert ref.file_name == "login page.png"
    assert ref.caption == ""
    assert ref.normalized_tag == "!/pro/projects/1/nodes/2/attachments/login page.png!"


def test_find_dradis_image_reference_parses_metadata_and_caption():
    ref = dradis.find_dradis_image_reference("!{width:95.0%}/pro/projects/1/nodes/2/attachments/login.png(The login page)!")

    assert ref.display_metadata == {"width": "95.0%"}
    assert ref.file_name == "login.png"
    assert ref.caption == "The login page"


def test_find_dradis_image_reference_parses_repeated_metadata_and_bold_caption():
    ref = dradis.find_dradis_image_reference("!{width:95.0%}{height:50%}/projects/1/nodes/2/attachments/image.png**(Sample caption)**!")

    assert ref.display_metadata == {"width": "95.0%", "height": "50%"}
    assert ref.file_name == "image.png"
    assert ref.caption == "Sample caption"
    assert ref.normalized_tag == "!/projects/1/nodes/2/attachments/image.png!"


def test_find_dradis_image_reference_returns_none_without_marker():
    assert dradis.find_dradis_image_reference("plain text with no image") is None
    assert dradis.find_dradis_image_reference("not an image !just exclaimed!") is None


def test_get_single_dradis_issue_and_target_node_label():
    assert dradis.get_single_dradis_issue([{"title": "only"}]) == {"title": "only"}
    assert dradis.get_single_dradis_issue([{"a": 1}, {"b": 2}]) == {}

    nodes = [
        {"label": "Report content"},
        {"label": "Uploaded files"},
        {"label": "10.0.0.1"},
    ]
    assert dradis.get_dradis_target_node_label(nodes) == "10.0.0.1"


def test_normalize_severity_and_status():
    assert dradis.normalize_dradis_severity("info") == "Informational"
    assert dradis.normalize_dradis_severity("informational") == "Informational"
    assert dradis.normalize_dradis_severity("Critical") == "Critical"
    assert dradis.normalize_dradis_severity("unknown") == "Informational"

    assert dradis.normalize_dradis_status("ready_for_review") == "Open"
    assert dradis.normalize_dradis_status("in progress") == "In Process"
    assert dradis.normalize_dradis_status("closed") == "Closed"
    assert dradis.normalize_dradis_status("new") == "Open"
