from os import path
import re


def test_skip_report_file_gets_created(skip_report_file):
    assert path.isfile(skip_report_file), "Skip report file has not been created!"


def test_correct_address_gets_reported_to_skip(
    skip_report_file, offline_validator_address
):
    with open(skip_report_file) as file:
        first_skip_report_entry = file.readline()

    assert first_skip_report_entry, "No validator has been reported to have skip!"

    pattern = f"[0-9]+,{offline_validator_address},[0-9,-]+"

    assert re.match(
        pattern, first_skip_report_entry
    ), "The first skip report entry does not report correct address of offline validator!"
