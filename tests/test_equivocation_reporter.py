import pytest
from unittest.mock import Mock
from monitor.equivocation_reporter import EquivocationReporter
from tests.data_generation import random_private_key, make_block


@pytest.fixture(scope="session")
def block_proposer_one_privkey():
    return random_private_key()


@pytest.fixture(scope="session")
def block_proposer_two_privkey(block_proposer_one_privkey):
    privkey = block_proposer_one_privkey

    while privkey == block_proposer_one_privkey:
        privkey = random_private_key()

    return privkey


@pytest.fixture
def report_callback():
    return Mock()


@pytest.fixture
def equivocation_reporter_with_callback(empty_db, report_callback):
    equivocation_reporter = EquivocationReporter(empty_db)
    equivocation_reporter.register_report_callback(report_callback)
    return equivocation_reporter


@pytest.mark.parametrize("branch_length", [1, 2, 4, 10])
def test_report_no_equivocation_for_a_single_branch(
    branch_length,
    block_proposer_one_privkey,
    report_callback,
    equivocation_reporter_with_callback,
    empty_db,
):
    for height in range(1, branch_length):
        block = make_block(proposer_privkey=block_proposer_one_privkey, height=height)
        empty_db.insert(block)
        equivocation_reporter_with_callback(block)

    report_callback.assert_not_called()


def test_report_no_equivocation_for_two_different_validators(
    block_proposer_one_privkey,
    block_proposer_two_privkey,
    report_callback,
    equivocation_reporter_with_callback,
    empty_db,
):
    height = 1

    block_one = make_block(proposer_privkey=block_proposer_one_privkey, height=height)
    block_two = make_block(proposer_privkey=block_proposer_two_privkey, height=height)

    empty_db.insert(block_one)
    empty_db.insert(block_two)

    equivocation_reporter_with_callback(block_one)
    equivocation_reporter_with_callback(block_two)

    report_callback.assert_not_called()


@pytest.mark.parametrize("number_of_blocks", [2, 4, 20])
def test_report_equivocation(
    number_of_blocks,
    block_proposer_one_privkey,
    report_callback,
    equivocation_reporter_with_callback,
    empty_db,
):
    height = 1
    proposed_block_hashes = []

    for _ in range(0, number_of_blocks):
        block = make_block(proposer_privkey=block_proposer_one_privkey, height=height)
        empty_db.insert(block)
        equivocation_reporter_with_callback(block)
        proposed_block_hashes.append(bytes(block.hash))

    assert number_of_blocks - 1 == report_callback.call_count

    for call in report_callback.call_args_list:
        args, _ = call  # Only the *args are of interest.
        retrieved_block_hashes = args[
            0
        ]  # The first and only argument is the list of block hashes.

        for block_hash in retrieved_block_hashes:
            assert block_hash in proposed_block_hashes
