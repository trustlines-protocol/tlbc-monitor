from os import path
import json


def test_offline_report_file_get_created(
    offline_report_file_path_list, offline_validator_address
):
    assert len(offline_report_file_path_list) == 1

    offline_report_file_path = offline_report_file_path_list[0]

    assert path.exists(offline_report_file_path)
    assert path.isfile(offline_report_file_path)


def test_offline_reports_content_is_correct(
    offline_report_file_path_list,
    offline_validator_address,
    get_skip_report_step_by_index,
):
    assert (
        offline_report_file_path_list
    ), "No validator has been reported to be offline!"

    offline_report_file_path = offline_report_file_path_list[0]

    with open(offline_report_file_path) as file:
        offline_report = json.load(file)

    # This holds true as long as the offline window is set in a manner that it
    # reports for the first detected missed step.
    assert offline_report == {
        "validator": offline_validator_address,
        "missed_steps": [get_skip_report_step_by_index(0)],
    }
