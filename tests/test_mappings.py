import mappings
from csv_parser import CSVParser


def test_example_mapping_keys_exist_in_csv_parser_data_mapping():
    valid_mapping_keys = set(CSVParser().get_data_mapping_ids())

    for map_type in mappings.MapType:
        spec = mappings.resolve(map_type.value)
        invalid_keys = {
            header: item["mapping_key"]
            for header, item in spec.mapping.items()
            if item["mapping_key"] not in valid_mapping_keys
        }

        assert invalid_keys == {}


def test_resolve_returns_example_csv_spec():
    spec = mappings.resolve(mappings.MapType.EXAMPLE_CSV.value)

    assert spec.mapping is mappings.example_csv_template_mapping
    assert spec.load_data_function is mappings.load_data_file_general_csv
    assert spec.verify_function is mappings.verify_example_csv_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_example_csv


def test_resolve_returns_example_json_spec():
    spec = mappings.resolve(mappings.MapType.EXAMPLE_JSON.value)

    assert spec.mapping is mappings.example_json_template_mapping
    assert spec.load_data_function is mappings.load_data_file_general_json
    assert spec.verify_function is mappings.verify_example_json_payload
    assert spec.temp_csv_function is mappings.create_temp_data_csv_example_json
