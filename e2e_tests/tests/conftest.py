import pytest
import os
import glob
import re


@pytest.fixture(scope="session")
def offline_validator_address():
    """Ethereum address of the offline validator.

    The offline validator is the third positioned validator at the
    e2e_test_chain. He is meant to be not started at all and therefore becomes
    reported as offline.
    """
    return "0xe7a664509027ff348d379bb5d3a8340aaecb56eb"


@pytest.fixture(scope="session")
def report_directory_path():
    """Path to directory where monitor write report files to.

    This must point to the directory which is mounted to the monitor service
    container to read issued reports.
    """
    base_directory = os.path.realpath(
        os.path.join(os.path.dirname(__file__), os.pardir)
    )

    return os.path.join(base_directory, "reports")


@pytest.fixture(scope="session")
def skip_report_file_path(report_directory_path):
    """Path to file where the monitor report skipped steps."""
    return os.path.join(report_directory_path, "skips")


@pytest.fixture(scope="session")
def skip_report_list(skip_report_file_path):
    """List of skip report entries from the associated file."""
    with open(skip_report_file_path) as file:
        return file.readlines()


@pytest.fixture(scope="session")
def offline_report_file_path_list(report_directory_path, offline_validator_address):
    """List of file paths for offline reports.

    Each entry is a file of an offline report by the monitor. The reports are
    filtered by the address of the offline validator. This list can be empty if
    no report has been issued.
    """
    file_name_pattern = f"offline_report_{offline_validator_address}_steps_*"
    file_path_pattern = os.path.join(report_directory_path, file_name_pattern)
    return glob.glob(file_path_pattern)


@pytest.fixture(scope="session")
def get_skip_report_step_by_index(skip_report_list):
    """Parse the missed step from skip a report.

    Based on the index within the skip report file (each line a report), the
    missed step for this entry gets extracted. In case no step could be found,
    the whole entry could not been parsed or no report for this index exists,
    the step is 'None'.
    """

    def extract_step(index):
        skip_report_entry = (
            skip_report_list[index] if index < len(skip_report_list) else ""
        )
        step_findings = re.findall(
            "^([0-9]+),0x[0-9,a-f]+,[0-9,-]+ [0-9,:]+$", skip_report_entry.strip()
        )
        step = int(step_findings[0]) if len(step_findings) == 1 else None
        return step

    return extract_step


@pytest.fixture(scope="session")
def get_skip_report_address_by_index(skip_report_list):
    """Parse validator address from skip report.

    Based on the index within the skip report file (each line a report), the
    validator address for this entry gets extracted. In case no address could be
    found, the whole entry could not been parsed or no report for this index
    exists, the address is 'None'.
    """

    def extract_address(index):
        skip_report_entry = (
            skip_report_list[index] if index < len(skip_report_list) else ""
        )
        address_findings = re.findall(
            "^[0-9]+,(0x[0-9,a-f]+?),[0-9,-]+ [0-9,:]+$", skip_report_entry.strip()
        )
        address = address_findings[0] if len(address_findings) == 1 else None
        return address

    return extract_address
