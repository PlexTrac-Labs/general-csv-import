import json

import utils.general_utils as utils


def test_save_json_as_ptrac_file_uses_report_name_and_increments(tmp_path):
    ptrac_data = {"report_info": {"name": "Report Name"}}

    utils.save_json_as_ptrac_file(ptrac_data, folder_path=str(tmp_path))
    utils.save_json_as_ptrac_file(ptrac_data, folder_path=str(tmp_path))

    first_file = tmp_path / "Report Name.ptrac"
    second_file = tmp_path / "Report Name (1).ptrac"
    assert first_file.exists()
    assert second_file.exists()
    assert json.loads(first_file.read_text()) == ptrac_data


def test_calculate_cvss3_base_score_accepts_prefixed_vector():
    score = utils.calculate_cvss3_base_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")

    assert score == 9.8
