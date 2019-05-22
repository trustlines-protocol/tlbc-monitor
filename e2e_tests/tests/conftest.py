import pytest
import os
import re


@pytest.fixture(scope="session")
def offline_validator_address():
    return "0xe7a664509027ff348d379bb5d3a8340aaecb56eb"


@pytest.fixture(scope="session")
def report_directory():
    base_directory = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.pardir
    )
    return os.path.join(base_directory, "reports")


@pytest.fixture(scope="session")
def skip_report_file(report_directory):
    return os.path.join(report_directory, "skips")


@pytest.fixture(scope="session")
def offline_report_file(report_directory, offline_validator_address):
    # TODO: encounter a more elegant way to handle the unknown step without need
    # to throw here
    for file_name in os.listdir(report_directory):
        print(file_name)
        if re.match(
            f"offline_report_{offline_validator_address}_steps_[0-9]+_to_[0-9]+",
            file_name,
        ):
            offline_report_file_name = file_name
            break

    else:
        assert False, "Could not find offline report file for offline validator!"

    return os.path.join(report_directory, offline_report_file_name)
