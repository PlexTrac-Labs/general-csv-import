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
