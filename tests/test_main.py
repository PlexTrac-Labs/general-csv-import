import argparse
import zipfile

import pytest

import main
import mappings
import utils.input_utils as input_utils


def test_argument_parser_uses_config_defaults(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        "data_file_path: data.csv\n"
        "headers_file_path: header_mapping.csv\n"
        "api_version: 3.1.0\n"
    )
    monkeypatch.chdir(tmp_path)

    args = main.parse_args([])

    assert args.data_file_path == "data.csv"
    assert args.headers_file_path == "header_mapping.csv"
    assert args.api_version == "3.1.0"


def test_argument_parser_cli_values_override_config(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        "data_file_path: config-data.csv\n"
        "headers_file_path: config-mapping.csv\n"
        "api_version: 3.1.0\n"
    )
    monkeypatch.chdir(tmp_path)

    args = main.parse_args([
        "--data-file-path", "cli-data.csv",
        "--headers-file-path", "cli-mapping.csv",
        "--api-version", "3.2.1",
    ])

    assert args.data_file_path == "cli-data.csv"
    assert args.headers_file_path == "cli-mapping.csv"
    assert args.api_version == "3.2.1"


def test_argument_parser_does_not_accept_input_alias(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    parser = main.create_argument_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--input", "data.csv"])


def test_argument_parser_uses_data_folder_path_config_default(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("data_folder_path: input_files/group\n")
    monkeypatch.chdir(tmp_path)

    args = main.parse_args([])

    assert args.data_folder_path == "input_files/group"
    assert args.data_file_path == ""


def test_argument_parser_preserves_both_file_and_folder_until_execution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    args = main.parse_args([
        "--data-file-path", "one.csv",
        "--data-folder-path", "a_folder",
    ])

    assert args.data_file_path == "one.csv"
    assert args.data_folder_path == "a_folder"


def test_argument_parser_accepts_template_and_layout(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text("findings_layout_name: Config Layout\n")
    monkeypatch.chdir(tmp_path)

    args = main.parse_args([
        "--report-template-name", "CLI Template",
    ])

    assert args.report_template_name == "CLI Template"
    assert args.findings_layout_name == "Config Layout"
    assert args.force_generate_ptrac is False


def test_determine_input_mode_non_interactive_ambiguity_uses_file(monkeypatch):
    input_utils.set_interactive_mode(False)
    args = argparse.Namespace(data_file_path="one.csv", data_folder_path="a_folder")

    assert main.determine_input_mode(args) == "file"


def test_determine_input_mode_interactive_ambiguity_prompts(monkeypatch):
    input_utils.set_interactive_mode(True)
    monkeypatch.setattr(input_utils, "user_options", lambda *a, **k: "folder")
    args = argparse.Namespace(data_file_path="one.csv", data_folder_path="a_folder")

    try:
        assert main.determine_input_mode(args) == "folder"
    finally:
        input_utils.set_interactive_mode(False)


def test_determine_input_mode_single_values():
    assert main.determine_input_mode(argparse.Namespace(data_file_path="x.csv", data_folder_path="")) == "file"
    assert main.determine_input_mode(argparse.Namespace(data_file_path="", data_folder_path="d")) == "folder"
    assert main.determine_input_mode(argparse.Namespace(data_file_path="", data_folder_path="")) is None


def test_get_input_file_paths_folder_modes(tmp_path):
    input_utils.set_interactive_mode(False)

    # csv folder
    (tmp_path / "b.csv").write_text("x")
    (tmp_path / "a.csv").write_text("x")
    args = argparse.Namespace(data_file_path="", data_folder_path=str(tmp_path))
    assert main.get_input_file_paths(args, mappings.resolve("example_csv")) == [str(tmp_path / "a.csv"), str(tmp_path / "b.csv")]

    # json folder
    (tmp_path / "c.json").write_text("{}")
    assert main.get_input_file_paths(args, mappings.resolve("example_json")) == [str(tmp_path / "c.json")]

    # CSV-driven Dradis folder mode only returns CSV files with paired ZIPs.
    with zipfile.ZipFile(tmp_path / "a.zip", "w") as zip_ref:
        zip_ref.writestr("dradis-repository.xml", "<x/>")
    assert main.get_input_file_paths(args, mappings.resolve("example_dradis_csv")) == [str(tmp_path / "a.csv")]

    # ZIP-driven Dradis folder mode returns Dradis ZIP exports.
    with zipfile.ZipFile(tmp_path / "dradis.zip", "w") as zip_ref:
        zip_ref.writestr("dradis-repository.xml", "<x/>")
    assert main.get_input_file_paths(args, mappings.resolve("example_dradis_zip")) == [
        str(tmp_path / "a.zip"),
        str(tmp_path / "dradis.zip"),
    ]


def test_run_processes_each_folder_input_and_saves_ptracs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    input_utils.set_interactive_mode(False)

    data_dir = tmp_path / "inputs"
    data_dir.mkdir()
    header = "client_name,report_name,title,severity,status,description\n"
    (data_dir / "a.csv").write_text(header + "Acme,Report A,Finding 1,High,Open,desc\n")
    (data_dir / "b.csv").write_text(header + "Acme,Report B,Finding 2,Low,Open,desc\n")

    out_dir = tmp_path / "out"
    args = main.parse_args([
        "--type", "example_csv",
        "--data-folder-path", str(data_dir),
        "--api-version", "2.19.0",
        "--output-dir", str(out_dir),
    ])

    main.run(args)

    generated = list(out_dir.glob("*.ptrac"))
    assert len(generated) == 2
