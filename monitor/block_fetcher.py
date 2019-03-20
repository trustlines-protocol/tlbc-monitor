import itertools
from typing import Any, NamedTuple

import structlog

from monitor.db import AlreadyExists


class BlockFetcherStateV1(NamedTuple):
    head: Any
    current_branch: Any


class BlockFetcher:
    """Fetches new blocks via a web3 interface and passes them on to a set of callbacks."""

    logger = structlog.get_logger("monitor.block_fetcher")

    def __init__(self, state, w3, db, max_reorg_depth=1000, initial_blocknr=0):
        self.w3 = w3
        self.db = db
        self.max_reorg_depth = max_reorg_depth

        self.head = state.head
        self.current_branch = state.current_branch

        self.report_callbacks = []
        self.initial_blocknr = initial_blocknr

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @classmethod
    def get_fresh_state(cls):
        return BlockFetcherStateV1(head=None, current_branch=[])

    @property
    def state(self):
        return BlockFetcherStateV1(head=self.head, current_branch=self.current_branch)

    def register_report_callback(self, callback):
        self.report_callbacks.append(callback)

    def _run_callbacks(self, blocks):
        for block in blocks:
            # XXX block_fetcher currently does no callbacks for the first block
            # see https://github.com/trustlines-network/tlbc-monitor/issues/12
            # we reproduce that bug here on purpose for the moment (i.e. too
            # lazy to fix the tests)
            if block.number == 0:
                continue

            for callback in self.report_callbacks:
                callback(block)

    def _insert_branch(self, blocks):
        if len(blocks) == 0:
            return

        if blocks[0].number not in (0, self.initial_blocknr) and not self.db.contains(
            blocks[0].parentHash
        ):
            raise ValueError("Tried to insert block with unknown parent")

        try:
            self.db.insert_branch(blocks)
            self.head = blocks[-1]
            self.current_branch.clear()
        except AlreadyExists:
            raise ValueError("Tried to insert already known block")

        self._run_callbacks(blocks)

    def _insert_first_block(self):
        if self.initial_blocknr < 0:
            self.initial_blocknr = max(
                0, self.w3.eth.blockNumber + self.initial_blocknr
            )

        self.logger.info(f"starting initial sync from block #{self.initial_blocknr}")
        block = self.w3.eth.getBlock(self.initial_blocknr)
        self._insert_branch([block])

    def fetch_and_insert_new_blocks(self, max_number_of_blocks=5000):
        """Fetches up to `max_number_of_blocks` blocks and updates the internal state
            If a full branch is fetched it also inserts the new blocks
            Returns the number of fetched blocks
        """
        number_of_synced_blocks = 0

        if self.db.is_empty():
            self._insert_first_block()
            number_of_synced_blocks += 1

        # sync forwards at most up until the forward sync target, but no more than
        # max_number_of_blocks
        max_forward_sync_blocks = max(
            0,
            min(
                max_number_of_blocks - number_of_synced_blocks,
                self.fetch_forward_sync_target() - self.head.number,
            ),
        )
        if max_forward_sync_blocks > 0:
            number_of_synced_blocks += self._sync_forwards(max_forward_sync_blocks)

        # sync backwards until we have synced max_number_of_blocks in total or we are fully synced
        assert 0 <= number_of_synced_blocks <= max_number_of_blocks
        max_backward_sync_blocks = max_number_of_blocks - number_of_synced_blocks
        if max_backward_sync_blocks > 0:
            number_of_synced_blocks += self._sync_backwards(max_backward_sync_blocks)

        return number_of_synced_blocks

    def fetch_forward_sync_target(self):
        return max(self.w3.eth.blockNumber - self.max_reorg_depth, 0)

    def _should_sync_forwards(self, current_block_number):
        return current_block_number - self.head.number > self.max_reorg_depth

    def _sync_forwards(self, max_number_of_blocks):
        block_numbers_to_fetch = range(
            self.head.number + 1, self.head.number + 1 + max_number_of_blocks
        )

        blocks = list(
            itertools.takewhile(
                lambda block: block is not None,
                (
                    self.w3.eth.getBlock(block_number)
                    for block_number in block_numbers_to_fetch
                ),
            )
        )

        self._insert_branch(blocks)
        return len(blocks)

    def _sync_backwards(self, max_blocks_to_fetch):
        branch_length_before = len(self.current_branch)
        complete = self._fetch_branch(max_blocks_to_fetch)
        number_of_fetched_blocks = len(self.current_branch) - branch_length_before

        if complete and len(self.current_branch) > 0:
            self._insert_branch(list(reversed(self.current_branch)))

        return number_of_fetched_blocks

    def _fetch_branch(self, max_blocks_to_fetch):
        if max_blocks_to_fetch <= 0:
            raise ValueError("Maximum number of blocks to fetch must be positive")

        if len(self.current_branch) == 0:
            head = self.w3.eth.getBlock("latest")
            if self.db.contains(head.hash):
                self.logger.info(
                    "no new blocks",
                    head_hash=self.head.hash,
                    head_number=self.head.number,
                )
                return True

            self.current_branch = [head]

        number_of_fetched_blocks = 0
        while not self.db.contains(self.current_branch[-1].parentHash):
            parent = self.w3.eth.getBlock(self.current_branch[-1].parentHash)
            self.current_branch.append(parent)

            number_of_fetched_blocks += 1
            if number_of_fetched_blocks >= max_blocks_to_fetch:
                break

        complete = self.db.contains(self.current_branch[-1].parentHash)
        return complete

    def get_sync_status_percentage(self):
        last_block_number = self.w3.eth.blockNumber
        head_block_number = self.head_block_number
        return head_block_number / last_block_number * 100

    @property
    def head_block_number(self):
        if self.head is None:
            return 0
        return self.head.number
