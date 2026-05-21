import pytest

import main


def test_argument_parser_uses_config_defaults(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(
        "data_file_path: data.csv\n"
        "headers_file_path: header_mapping.csv\n"
        "api_version: 3.1.0\n"
    )
    monkeypatch.chdir(tmp_path)

    parser = main.create_argument_parser()
    args = parser.parse_args([])

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

    parser = main.create_argument_parser()
    args = parser.parse_args([
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
