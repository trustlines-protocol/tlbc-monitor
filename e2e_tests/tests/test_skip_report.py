from os import path
import re


def test_skip_report_file_gets_created(skip_report_file_path):
    assert path.isfile(skip_report_file_path), "Skip report file has not been created!"


def test_correct_address_gets_reported_to_skip(
    skip_report_list, offline_validator_address
):
    assert skip_report_list, "No validator has been reported to have skipped!"

    for skip_report_entry in skip_report_list:
        reported_addresses_findings = re.findall(
            "^[0-9]+,(0x[0-9,a-f]+?),[0-9,-]+ [0-9,:]+$", skip_report_entry.strip()
        )

        assert len(reported_addresses_findings) == 1
        assert reported_addresses_findings[0] == offline_validator_address
