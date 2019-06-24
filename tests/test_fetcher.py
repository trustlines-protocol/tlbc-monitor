import pytest
from unittest.mock import Mock, call

from monitor.block_fetcher import BlockFetcher, FetchingForkWithUnkownBaseError
from monitor.blocksel import ResolveBlockByNumber, ResolveGenesisBlock


@pytest.fixture
def report_callback():
    return Mock()


@pytest.fixture
def max_reorg_depth():
    return 3


@pytest.fixture
def block_fetcher(w3, empty_db, report_callback, max_reorg_depth):
    block_fetcher = BlockFetcher.from_fresh_state(
        w3, empty_db, max_reorg_depth=max_reorg_depth
    )
    block_fetcher.register_report_callback(report_callback)
    return block_fetcher


def test_genesis(w3, block_fetcher):
    genesis = w3.eth.getBlock(0)
    block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=1)
    assert block_fetcher.head == genesis


def test_fetch_single_blocks(eth_tester, block_fetcher, report_callback):
    block_fetcher.fetch_and_insert_new_blocks()  # genesis
    report_callback.reset_mock()
    for block_number in range(1, 100):
        eth_tester.mine_blocks(1)
        block_fetcher.fetch_and_insert_new_blocks()
        report_callback.assert_called_once()
        assert report_callback.call_args[0][0].number == block_number
        report_callback.reset_mock()


def test_fetch_multiple_blocks(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(3)
    block_fetcher.fetch_and_insert_new_blocks()
    assert report_callback.call_count == 4
    assert [call_args[0][0].number for call_args in report_callback.call_args_list] == [
        0,
        1,
        2,
        3,
    ]


def test_number_of_fetched_blocks(eth_tester, block_fetcher):
    eth_tester.mine_blocks(8)
    assert (
        block_fetcher.fetch_and_insert_new_blocks() == 1 + 8
    )  # genesis + mined blocks
    eth_tester.mine_blocks(5)
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=2) == 2


# test 4,5, 6, because 5 is forward/backward switch number
@pytest.mark.parametrize("max_block_height", [4, 5, 6])
def test_max_block_height_of_fetched_blocks(
    eth_tester, w3, block_fetcher, max_block_height
):
    eth_tester.mine_blocks(8)
    assert w3.eth.blockNumber == 8
    assert (
        block_fetcher.fetch_and_insert_new_blocks(max_block_height=max_block_height)
        == max_block_height + 1
    )
    assert block_fetcher.head.number == max_block_height
    assert (
        block_fetcher.fetch_and_insert_new_blocks(max_block_height=max_block_height)
        == 0
    )
    assert block_fetcher.head.number == max_block_height


def test_fail_to_sync_from_block_number_that_does_not_exist(block_fetcher):
    # Work on the chain with only the genesis block.
    block_fetcher.initial_block_resolver = ResolveBlockByNumber(1)

    with pytest.raises(ValueError):
        block_fetcher.fetch_and_insert_new_blocks()


def test_forward_backward_sync_transition(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(10)

    # forward sync until block 5
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=6) == 6
    assert block_fetcher.head.number == 5
    assert len(block_fetcher.current_branch) == 0
    assert report_callback.call_count == 6
    report_callback.reset_mock()

    # sync blocks 6 to 7 forwards, start backward sync with block 10
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=3) == 3
    assert block_fetcher.head.number == 7
    assert len(block_fetcher.current_branch) == 1
    assert report_callback.call_count == 2
    report_callback.reset_mock()

    # finish backward sync (block 8 and 9)
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=2) == 2
    assert len(block_fetcher.current_branch) == 0
    assert block_fetcher.head.number == 10
    assert report_callback.call_count == 3
    report_callback.reset_mock()


def test_always_finish_backwards_sync(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(3)

    # start backwards sync
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=2) == 2
    assert block_fetcher.head.number == 0
    assert report_callback.call_count == 1  # only genesis
    report_callback.reset_mock()

    # mine lots of new blocks that would trigger forwards sync if backwards sync were not already in
    # progress
    eth_tester.mine_blocks(10)

    # finish backwards sync
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=10) == 2
    assert block_fetcher.head.number == 3
    assert report_callback.call_count == 3
    report_callback.reset_mock()

    # only now start forward sync
    assert block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=3) == 3
    assert block_fetcher.head.number == 6
    assert report_callback.call_count == 3
    report_callback.reset_mock()


def test_fetch_multiple_blocks_with_max_number_of_blocks(
    eth_tester, block_fetcher, report_callback
):
    eth_tester.mine_blocks(3)
    block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=3)
    assert [call_args[0][0].number for call_args in report_callback.call_args_list] == [
        0
    ]
    block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=1)
    assert [call_args[0][0].number for call_args in report_callback.call_args_list] == [
        0,
        1,
        2,
        3,
    ]


def test_fetch_exact_number_of_blocks(eth_tester, block_fetcher, report_callback):
    eth_tester.mine_blocks(5)
    block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=6)
    assert report_callback.call_count == 6


def test_noticed_reorg(w3, eth_tester, block_fetcher, report_callback):
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # mine some common blocks
    common_hashes = [0]  # genesis
    common_hashes.extend(eth_tester.mine_blocks(2, coinbase=coinbase1))
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
    assert (
        report_callback.call_args_list
        == common_reports + fork_a_reports + fork_b_reports
    )


@pytest.mark.parametrize(
    "max_reorg_depth, number_of_reorged_blocks", [(1, 1), (1, 10), (5, 1), (5, 30)]
)
def test_fail_on_fetching_fork_when_sync_forwards(
    block_fetcher, eth_tester, max_reorg_depth, number_of_reorged_blocks
):
    """Test behavior on forks while sync forwards.

    The block fetcher synchronize the whole chain. Afterwards the blockchain
    becomes reorganized by a parametrized number of blocks. The block fetcher is
    idle for that many blocks on the new fork, that forward syncing will be
    used. This should fail due to fetching blocks from a fork without any hash
    pointer to the old branch.

    TODO: In future the fetcher should be safe against reorganizations by less
    blocks than the configured max_reorg_depth, which is not the case as shown
    here.
    """

    block_fetcher.max_reorg_depth = max_reorg_depth
    block_fetcher.initial_block_resolver = ResolveGenesisBlock()
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # Create first branch at least as long as the max_reorg_depth
    length_first_branch = max(max_reorg_depth, number_of_reorged_blocks)
    eth_tester.mine_blocks(length_first_branch - number_of_reorged_blocks)
    fork_snapshot_id = eth_tester.take_snapshot()
    eth_tester.mine_blocks(number_of_reorged_blocks, coinbase=coinbase1)

    # Fetch first branch considered as safe.
    block_fetcher.fetch_and_insert_new_blocks()

    # Create fork with enough blocks to synchronize forward.
    eth_tester.revert_to_snapshot(fork_snapshot_id)
    eth_tester.mine_blocks(
        number_of_reorged_blocks + max_reorg_depth + 2, coinbase=coinbase2
    )

    #  Try to fetch blocks based on the new fork.
    with pytest.raises(FetchingForkWithUnkownBaseError):
        block_fetcher.fetch_and_insert_new_blocks()


@pytest.mark.parametrize(
    (
        "max_reorg_depth",
        "initial_block_number",
        "number_of_blocks_before_initial_height_to_fork",
        "number_of_blocks_on_fork_after_initial_block",
    ),
    [
        # Default random constellation as base
        (3, 10, 2, 2),
        # Minimum initial_block_number related to number_of_blocks_before_initial_height_to_fork
        (3, 2, 2, 2),
        # Random height value for initial_block_number
        (3, 30, 2, 2),
        # Minimal number_of_blocks_before_initial_height_to_fork
        (3, 10, 1, 2),
        # Maximum number_of_blocks_before_initial_height_to_fork related to initial_block_number
        (3, 10, 10, 2),
        # Minimum number_of_blocks_on_fork_after_initial_block
        (3, 10, 2, 1),
        # Maximum number_of_blocks_on_fork_after_initial_block related related to max_reorg_path
        (3, 10, 2, 4),
    ],
)
def test_fail_on_fetching_fork_based_on_block_before_inital_one_when_sync_backwards(
    block_fetcher,
    eth_tester,
    max_reorg_depth,
    initial_block_number,
    number_of_blocks_before_initial_height_to_fork,
    number_of_blocks_on_fork_after_initial_block,
):
    """Test behavior on forks to blocks before initial block while sync backwards.

    Notice that the max_reorg_depth is artificially set to a not safe enough
    value here.
    The block fetcher synchronize the chain from the initial chain
    up to the head. Afterwards the blockchain becomes reorganized based on
    a block before the initial synced one. Trying to sync backwards on the new
    fork should fail.
    The parametrization describes the range of constellations in which the block
    fetcher will synchronize backwards after the chain has forked.
    """

    # Ensure that parameter lead to backward syncing.
    assert number_of_blocks_before_initial_height_to_fork <= initial_block_number
    assert number_of_blocks_on_fork_after_initial_block <= max_reorg_depth + 1

    block_fetcher.max_reorg_depth = max_reorg_depth
    block_fetcher.initial_block_resolver = ResolveBlockByNumber(initial_block_number)
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # Create first branch
    # Make sure to seal enough blocks after the original initial_block_number,
    # to make sure it get not adjusted to a save version by the max_reorg_depth.
    eth_tester.mine_blocks(
        initial_block_number - number_of_blocks_before_initial_height_to_fork,
        coinbase=coinbase1,
    )
    fork_snapshot_id = eth_tester.take_snapshot()
    eth_tester.mine_blocks(
        number_of_blocks_before_initial_height_to_fork + max_reorg_depth,
        coinbase=coinbase1,
    )

    # Fetch branch from initial block number.
    block_fetcher.fetch_and_insert_new_blocks()

    # Create fork based on block before initial synced one with less enough
    # blocks to synchronize backward.
    eth_tester.revert_to_snapshot(fork_snapshot_id)
    eth_tester.mine_blocks(
        number_of_blocks_before_initial_height_to_fork
        + number_of_blocks_on_fork_after_initial_block,
        coinbase=coinbase2,
    )

    #  Try to fetch blocks based on the new fork.
    with pytest.raises(FetchingForkWithUnkownBaseError):
        block_fetcher.fetch_and_insert_new_blocks()


def test_rediscovered_reorg(w3, eth_tester, block_fetcher, report_callback):
    coinbase1, coinbase2 = eth_tester.get_accounts()[:2]

    # mine some common blocks
    common_hashes = [0]  # genesis
    common_hashes.extend(eth_tester.mine_blocks(2, coinbase=coinbase1))
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
    new_block_hashes = [0]  # genesis
    new_block_hashes.extend(eth_tester.mine_blocks(6))
    reports = [call(w3.eth.getBlock(h)) for h in new_block_hashes]
    block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=4)

    restarted_block_fetcher = BlockFetcher(block_fetcher.state, w3, block_fetcher.db)
    restarted_block_fetcher.register_report_callback(report_callback)
    restarted_block_fetcher.fetch_and_insert_new_blocks(max_number_of_blocks=3)

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
        state=block_fetcher.state, w3=w3, db=block_fetcher.db
    )
    restarted_block_fetcher.register_report_callback(report_callback)
    restarted_block_fetcher.fetch_and_insert_new_blocks()
    assert report_callback.call_args_list == [
        call(w3.eth.getBlock(h)) for h in early_fork_a_hashes + late_fork_a_hashes
    ]
