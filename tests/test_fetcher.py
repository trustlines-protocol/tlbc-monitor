import pytest
from unittest.mock import (
    Mock,
    call,
)

from watchdog.block_fetcher import (
    BlockFetcher,
)


@pytest.fixture
def report_callback():
    return Mock()


@pytest.fixture
def max_reorg_depth():
    return 3


@pytest.fixture
def block_fetcher(w3, empty_db, report_callback, max_reorg_depth):
    block_fetcher = BlockFetcher.from_fresh_state(w3, empty_db, max_reorg_depth=max_reorg_depth)
    block_fetcher.register_report_callback(report_callback)
    return block_fetcher


def test_genesis(w3, block_fetcher):
    genesis = w3.eth.getBlock(0)
    block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=1)
    assert block_fetcher.head == genesis


def test_fetch_single_blocks(eth_tester, block_fetcher, report_callback):
    for block_number in range(1, 100):
        eth_tester.mine_blocks(1)
        block_fetcher.fetch_and_insert_new_blocks()
        report_callback.assert_called_once()
        assert report_callback.call_args[0][0].number == block_number
        report_callback.reset_mock()


def test_fetch_multiple_blocks(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(3)
    block_fetcher.fetch_and_insert_new_blocks()
    assert report_callback.call_count == 3
    assert [call_args[0][0].number for call_args in report_callback.call_args_list] == [1, 2, 3]


def test_number_of_fetched_blocks(eth_tester, block_fetcher):
    eth_tester.mine_blocks(8)
    assert block_fetcher.fetch_and_insert_new_blocks() == 1 + 8  # genesis + mined blocks
    eth_tester.mine_blocks(5)
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=2) == 2


def test_forward_backward_sync_transition(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(10)

    # forward sync until block 5
    assert block_fetcher.fetch_and_insert_new_blocks(6) == 6
    assert report_callback.call_count == 6 - 1  # genesis is not reported
    report_callback.reset_mock()

    # sync blocks 6 to 7 forwards, start backward sync with block 10
    assert block_fetcher.fetch_and_insert_new_blocks(3)
    assert report_callback.call_count == 2
    report_callback.reset_mock()

    # finish backward sync (block 8 and 9)
    assert block_fetcher.fetch_and_insert_new_blocks(2)
    assert report_callback.call_count == 3
    report_callback.reset_mock()


def test_fetch_multiple_blocks_with_max_number_of_blocks(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(3)
    block_fetcher.fetch_and_insert_new_blocks(2)
    report_callback.assert_not_called()
    block_fetcher.fetch_and_insert_new_blocks(1)
    assert [call_args[0][0].number for call_args in report_callback.call_args_list] == [1, 2, 3]


def test_fetch_exact_number_of_blocks(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(5)
    block_fetcher.fetch_and_insert_new_blocks(5)
    assert report_callback.call_count == 5


def test_noticed_reorg(w3, eth_tester, block_fetcher, report_callback):
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # mine some common blocks
    common_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)
    common_reports = [call(w3.eth.getBlock(h)) for h in common_hashes]

    # point of fork
    fork_snapshot_id = eth_tester.take_snapshot()

    # mine some blocks on fork A
    fork_a_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)
    fork_a_reports = [call(w3.eth.getBlock(h)) for h in fork_a_hashes]

    # fetch
    block_fetcher.fetch_and_insert_new_blocks()

    # mine on fork B
    eth_tester.revert_to_snapshot(fork_snapshot_id)
    fork_b_hashes = eth_tester.mine_blocks(2, coinbase=coinbase2)
    fork_b_reports = [call(w3.eth.getBlock(h)) for h in fork_b_hashes]

    # fetch again
    block_fetcher.fetch_and_insert_new_blocks()
    assert report_callback.call_args_list == common_reports + fork_a_reports + fork_b_reports


def test_rediscovered_reorg(w3, eth_tester, block_fetcher, report_callback):
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # mine some common blocks
    common_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)
    common_reports = [call(w3.eth.getBlock(h)) for h in common_hashes]

    # point of fork
    fork_snapshot_id = eth_tester.take_snapshot()

    # mine some blocks on fork A
    fork_a_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)
    fork_a_reports = [call(w3.eth.getBlock(h)) for h in fork_a_hashes]
    fork_a_head_snapshot_id = eth_tester.take_snapshot()

    # mine on fork B
    eth_tester.revert_to_snapshot(fork_snapshot_id)
    fork_b_hashes = eth_tester.mine_blocks(2, coinbase=coinbase2)
    fork_b_reports = [call(w3.eth.getBlock(h)) for h in fork_b_hashes]

    # fetch (will not find hidden fork A)
    block_fetcher.fetch_and_insert_new_blocks()

    # mine on A again to discover all blocks there
    eth_tester.revert_to_snapshot(fork_a_head_snapshot_id)
    new_fork_a_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)
    new_fork_a_reports = [call(w3.eth.getBlock(h)) for h in new_fork_a_hashes]

    # fetch and see fork A reappear
    block_fetcher.fetch_and_insert_new_blocks()
    assert report_callback.call_args_list == (
        common_reports + fork_b_reports + fork_a_reports + new_fork_a_reports
    )


def test_state_generation(eth_tester, block_fetcher):
    eth_tester.mine_blocks(3)
    block_fetcher.fetch_and_insert_new_blocks()

    assert block_fetcher.state.head == block_fetcher.head
    assert block_fetcher.state.current_branch == block_fetcher.current_branch


def test_restart(w3, eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(3)
    block_fetcher.fetch_and_insert_new_blocks()
    report_callback.reset_mock()

    new_block_hashes = eth_tester.mine_blocks(3)
    reports = [call(w3.eth.getBlock(h)) for h in new_block_hashes]
    restarted_block_fetcher = BlockFetcher(block_fetcher.state, w3, block_fetcher.db)
    restarted_block_fetcher.register_report_callback(report_callback)
    restarted_block_fetcher.fetch_and_insert_new_blocks()

    assert report_callback.call_args_list == reports


def test_restart_with_fetch(w3, eth_tester, block_fetcher, report_callback):
    new_block_hashes = eth_tester.mine_blocks(6)
    reports = [call(w3.eth.getBlock(h)) for h in new_block_hashes]
    block_fetcher.fetch_and_insert_new_blocks(3)

    restarted_block_fetcher = BlockFetcher(block_fetcher.state, w3, block_fetcher.db)
    restarted_block_fetcher.register_report_callback(report_callback)
    restarted_block_fetcher.fetch_and_insert_new_blocks(3)

    assert report_callback.call_args_list == reports


def test_restart_with_reorg(w3, eth_tester, block_fetcher, report_callback):
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # mine some common blocks
    eth_tester.mine_blocks(2, coinbase=coinbase1)

    # point of fork
    fork_snapshot_id = eth_tester.take_snapshot()

    # mine some blocks on fork A
    early_fork_a_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)
    fork_a_tip_snapshot_id = eth_tester.take_snapshot()

    # mine on fork B
    eth_tester.revert_to_snapshot(fork_snapshot_id)
    eth_tester.mine_blocks(2, coinbase=coinbase2)

    # fetch common and fork B
    block_fetcher.fetch_and_insert_new_blocks()
    report_callback.reset_mock()

    # mine on fork A again
    eth_tester.revert_to_snapshot(fork_a_tip_snapshot_id)
    late_fork_a_hashes = eth_tester.mine_blocks(2, coinbase=coinbase1)

    # restart block fetcher
    restarted_block_fetcher = BlockFetcher(
        state=block_fetcher.state,
        w3=w3,
        db=block_fetcher.db,
    )
    restarted_block_fetcher.register_report_callback(report_callback)
    restarted_block_fetcher.fetch_and_insert_new_blocks()
    assert report_callback.call_args_list == [
        call(w3.eth.getBlock(h)) for h in early_fork_a_hashes + late_fork_a_hashes
    ]
