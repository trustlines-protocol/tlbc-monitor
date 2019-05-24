import pytest
import os
import glob


@pytest.fixture(scope="session")
def offline_validator_address():
    return "0xe7a664509027ff348d379bb5d3a8340aaecb56eb"


@pytest.fixture(scope="session")
def report_directory_path():
    base_directory = os.path.realpath(
        os.path.join(os.path.dirname(__file__), os.pardir)
    )

    return os.path.join(base_directory, "reports")


@pytest.fixture(scope="session")
def skip_report_file_path(report_directory_path):
    return os.path.join(report_directory_path, "skips")


@pytest.fixture(scope="session")
def skip_report_list(skip_report_file_path):
    with open(skip_report_file_path) as file:
        return file.readlines()


@pytest.fixture(scope="session")
def offline_report_file_paths(report_directory_path, offline_validator_address):
    file_name_pattern = f"offline_report_{offline_validator_address}_steps_*"
    file_path_pattern = os.path.join(report_directory_path, file_name_pattern)
    return glob.glob(file_path_pattern)
