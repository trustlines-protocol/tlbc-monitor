from os import path
import re
import json


def get_missed_step_from_skip_report_entry(skip_report_entry):
    missed_step_findings = re.findall(
        "^([0-9]+),0x[0-9,a-f]+,[0-9,-]+ [0-9,:]+$", skip_report_entry.strip()
    )
    missed_step = (
        int(missed_step_findings[0]) if len(missed_step_findings) == 1 else None
    )
    return missed_step


def test_offline_report_file_get_created(offline_report_file_paths):
    assert len(offline_report_file_paths) > 0

    for file in offline_report_file_paths:
        assert path.isfile(file)


def test_offline_reports_content_is_correct(
    offline_report_file_paths, offline_validator_address, skip_report_list
):
    for index, report_file in enumerate(offline_report_file_paths):
        with open(report_file) as file:
            report = json.load(file)

        assert "validator" in report
        assert report["validator"] == offline_validator_address
        assert "missed_steps" in report

        missed_step_list = report["missed_steps"]

        assert isinstance(missed_step_list, list)
        assert len(missed_step_list) == 1

        missed_step = missed_step_list[0]

        assert isinstance(missed_step, int)

        # This holds true due to the offline window of size one.
        assert missed_step == get_missed_step_from_skip_report_entry(
            skip_report_list[index]
        )
