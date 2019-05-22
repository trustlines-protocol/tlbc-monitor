from os import path
import json


def test_offline_report_file_get_created(offline_report_file):
    assert path.isfile(offline_report_file), "Offline report file has not been created!"


def test_offline_report_content_is_correct(
    offline_report_file, offline_validator_address
):
    with open(offline_report_file) as file:
        report = json.loads(file.read())

    assert "validator" in report
    assert report["validator"] == offline_validator_address
    assert "missed_steps" in report

    missed_steps = report["missed_steps"]

    assert isinstance(missed_steps, list)
    assert len(missed_steps) == 1
    assert isinstance(missed_steps[0], int)
    # TODO: compare missed step number somehow...
