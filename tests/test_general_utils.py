import json

import utils.general_utils as utils


def test_save_json_as_ptrac_file_uses_client_report_timestamp_and_increments(tmp_path, monkeypatch):
    monkeypatch.setattr(utils.time, "time", lambda: 1234.56)
    monkeypatch.setattr(utils.time, "localtime", lambda timestamp: (2026, 5, 21, 13, 14, 15, 0, 0, 0))
    ptrac_data = {
        "client_info": {"name": "Client Name"},
        "report_info": {"name": "Report Name"},
    }

    utils.save_json_as_ptrac_file(ptrac_data, folder_path=str(tmp_path))
    utils.save_json_as_ptrac_file(ptrac_data, folder_path=str(tmp_path))

    first_file = tmp_path / "Client Name_Report Name_2026_05_21_13_14_15.ptrac"
    second_file = tmp_path / "Client Name_Report Name_2026_05_21_13_14_15 (1).ptrac"
    assert first_file.exists()
    assert second_file.exists()
    assert json.loads(first_file.read_text()) == ptrac_data


def test_calculate_cvss3_base_score_accepts_prefixed_vector():
    score = utils.calculate_cvss3_base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")

    assert score == 9.8


def test_try_parsing_date_accepts_full_month_names():
    parsed = utils.try_parsing_date("May 8, 2026")

    assert parsed.tm_year == 2026
    assert parsed.tm_mon == 5
    assert parsed.tm_mday == 8


def test_convert_textile_to_html_handles_basic_markup():
    if utils.textile is None:
        import pytest
        pytest.skip("textile is not installed")

    result = utils.convert_textile_to_html("*bold*")

    assert "<strong>bold</strong>" in result


def test_convert_textile_to_html_escapes_dradis_placeholder_and_angle_text():
    placeholder = utils.convert_textile_to_html("<dradis.placeholder>")
    assert "<dradis.placeholder>" not in placeholder
    assert "dradis.placeholder" in placeholder

    raw = utils.convert_textile_to_html("text <whales|elephants> and <p> literal")
    assert "<whales|elephants>" not in raw
    assert "whales|elephants" in raw


def test_escape_angle_brackets_escapes_both_directions():
    assert utils.escape_angle_brackets("<p>hi</p>") == "&lt;p&gt;hi&lt;/p&gt;"


def test_update_open_closing_tags_replaces_matching_and_nested_pairs():
    value = "`{outer `{inner}` outer}`"
    result = utils.update_open_closing_tags(value, "`{", "}`", "<code>", "</code>")

    assert result == "<code>outer <code>inner</code> outer</code>"


def test_update_open_closing_tags_only_strips_br_when_requested():
    value = "<b>keep<br /></b>"
    without_strip = utils.update_open_closing_tags(value, "<b>", "</b>", "<strong>", "</strong>")
    with_strip = utils.update_open_closing_tags(value, "<b>", "</b>", "<strong>", "</strong>", strip_br_tags=True)

    assert without_strip == "<strong>keep<br /></strong>"
    assert with_strip == "<strong>keep</strong>"


def test_strip_extra_lines_preserves_pre_code_content():
    value = "before\n\n\n<pre><code>line1\n\n\nline2</code></pre>\n\n\nafter"
    result = utils.strip_extra_lines(value, "description")

    assert "<pre><code>line1\n\n\nline2</code></pre>" in result
    # collapsed runs of blank lines outside the protected block
    assert "before\n<pre>" in result
