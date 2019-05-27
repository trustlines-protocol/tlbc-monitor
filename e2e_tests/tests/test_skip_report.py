from os import path


def test_skip_report_file_gets_created(skip_report_file_path):
    assert path.exists(skip_report_file_path)
    assert path.isfile(skip_report_file_path)


def test_correct_address_gets_reported_to_skip(
    skip_report_list, offline_validator_address, get_skip_report_address_by_index
):
    assert skip_report_list, "No validator has been reported to have skipped!"

    for index in range(len(skip_report_list)):
        assert get_skip_report_address_by_index(index) == offline_validator_address
