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


# ---- detect_cvss_version ----------------------------------------------------

def test_detect_cvss_version_recognises_all_three_versions():
    assert utils.detect_cvss_version("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "3.0"
    assert utils.detect_cvss_version("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "3.1"
    assert utils.detect_cvss_version("CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N") == "4.0"


def test_detect_cvss_version_returns_none_for_bare_or_unknown():
    assert utils.detect_cvss_version("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is None
    assert utils.detect_cvss_version("") is None
    assert utils.detect_cvss_version("CVSS:2.0/AV:N/AC:L/Au:N/C:C/I:C/A:C") is None


def test_detect_cvss_version_is_case_insensitive():
    assert utils.detect_cvss_version("cvss:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "3.1"
    assert utils.detect_cvss_version("Cvss:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N") == "4.0"


# ---- normalize_cvss_vector --------------------------------------------------

def test_normalize_cvss_vector_uppercases_prefix():
    assert utils.normalize_cvss_vector("cvss:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert utils.normalize_cvss_vector("Cvss:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N") == "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


def test_normalize_cvss_vector_leaves_bare_string_unchanged():
    bare = "AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    assert utils.normalize_cvss_vector(bare) == bare


def test_normalize_cvss_vector_strips_surrounding_whitespace():
    assert utils.normalize_cvss_vector("  cvss:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H  ") == "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"


# ---- is_valid_cvss3_vector --------------------------------------------------

def test_is_valid_cvss3_vector_accepts_bare_and_prefixed():
    assert utils.is_valid_cvss3_vector("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True
    assert utils.is_valid_cvss3_vector("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True


def test_is_valid_cvss3_vector_rejects_bad_metrics():
    assert utils.is_valid_cvss3_vector("AV:N/AC:L/PR:N/UI:INVALID") is False
    assert utils.is_valid_cvss3_vector("") is False


# ---- is_valid_cvss3_1_vector ------------------------------------------------

def test_is_valid_cvss3_1_vector_accepts_bare_and_prefixed():
    assert utils.is_valid_cvss3_1_vector("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True
    assert utils.is_valid_cvss3_1_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True


def test_is_valid_cvss3_1_vector_rejects_bad_metrics():
    assert utils.is_valid_cvss3_1_vector("AV:N/AC:L/PR:N/UI:INVALID") is False
    assert utils.is_valid_cvss3_1_vector("") is False


# ---- is_valid_cvss4_vector --------------------------------------------------

_VALID_CVSS40 = "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
_VALID_CVSS40_BODY = "AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"


def test_is_valid_cvss4_vector_accepts_valid_base_vectors():
    assert utils.is_valid_cvss4_vector(_VALID_CVSS40) is True
    assert utils.is_valid_cvss4_vector(_VALID_CVSS40_BODY) is True
    assert utils.is_valid_cvss4_vector("AV:P/AC:H/AT:P/PR:H/UI:A/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N") is True


def test_is_valid_cvss4_vector_rejects_missing_or_bad_metrics():
    # Missing AT metric
    assert utils.is_valid_cvss4_vector("AV:N/AC:L/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N") is False
    # Bad value for UI (3.x value R is not valid in 4.0)
    assert utils.is_valid_cvss4_vector("AV:N/AC:L/AT:N/PR:N/UI:R/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N") is False
    assert utils.is_valid_cvss4_vector("") is False


# ---- is_valid_cvss_vector ---------------------------------------------------

def test_is_valid_cvss_vector_accepts_all_three_versions():
    assert utils.is_valid_cvss_vector("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True
    assert utils.is_valid_cvss_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True
    assert utils.is_valid_cvss_vector(_VALID_CVSS40) is True


def test_is_valid_cvss_vector_accepts_lowercase_prefix():
    assert utils.is_valid_cvss_vector("cvss:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True
    assert utils.is_valid_cvss_vector("cvss:4.0/" + _VALID_CVSS40_BODY) is True


def test_is_valid_cvss_vector_accepts_bare_3x_string():
    assert utils.is_valid_cvss_vector("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") is True


def test_is_valid_cvss_vector_rejects_invalid():
    assert utils.is_valid_cvss_vector("not-a-vector") is False
    assert utils.is_valid_cvss_vector("") is False
    assert utils.is_valid_cvss_vector("AV:N/AC:L/PR:N/UI:INVALID") is False  # bad metric value


# ---- calculate_cvss_base_score ----------------------------------------------

def test_calculate_cvss_base_score_returns_score_for_3x():
    assert utils.calculate_cvss_base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8
    assert utils.calculate_cvss_base_score("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8
    assert utils.calculate_cvss_base_score("AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8


def test_calculate_cvss_base_score_normalises_lowercase_prefix():
    assert utils.calculate_cvss_base_score("cvss:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H") == 9.8


def test_calculate_cvss_base_score_returns_score_for_40():
    score = utils.calculate_cvss_base_score(_VALID_CVSS40)
    assert score is not None
    assert isinstance(score, float)
    assert 0.0 <= score <= 10.0


def test_calculate_cvss_base_score_returns_none_for_invalid():
    assert utils.calculate_cvss_base_score("not-a-vector") is None
    assert utils.calculate_cvss_base_score("") is None


def test_try_parsing_date_accepts_full_month_names():
    parsed = utils.try_parsing_date("May 8, 2026")

    assert parsed.tm_year == 2026
    assert parsed.tm_mon == 5
    assert parsed.tm_mday == 8
