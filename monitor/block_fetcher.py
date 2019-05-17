import datetime
import itertools
from typing import Any, NamedTuple

import structlog

from monitor.db import AlreadyExists
from monitor import blocksel


class BlockFetcherStateV1(NamedTuple):
    head: Any
    current_branch: Any
    initial_blocknr: int


class FetchingForkWithUnkownBaseError(Exception):
    pass


def format_block(block):
    dt = datetime.datetime.utcfromtimestamp(block.timestamp).replace(
        tzinfo=datetime.timezone.utc
    )
    return f"Block({block.number}, {dt.isoformat()})"


class BlockFetcher:
    """Fetches new blocks via a web3 interface and passes them on to a set of callbacks."""

    logger = structlog.get_logger("monitor.block_fetcher")

    def __init__(
        self, state, w3, db, max_reorg_depth=1000, initial_block_resolver=None
    ):
        self.w3 = w3
        self.db = db
        self.max_reorg_depth = max_reorg_depth

        self.head = state.head
        self.current_branch = state.current_branch

        self.report_callbacks = []
        self.initial_block_resolver = initial_block_resolver
        self.initial_blocknr = state.initial_blocknr

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @classmethod
    def get_fresh_state(cls):
        return BlockFetcherStateV1(head=None, current_branch=[], initial_blocknr=0)

    @property
    def state(self):
        return BlockFetcherStateV1(
            head=self.head,
            current_branch=self.current_branch,
            initial_blocknr=self.initial_blocknr,
        )

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
            raise FetchingForkWithUnkownBaseError(
                "Tried to insert branch from a fork with unknown parent block."
            )

        try:
            self.db.insert_branch(blocks)
            self.head = blocks[-1]
            self.current_branch.clear()
        except AlreadyExists:
            raise ValueError("Tried to insert already known block")

        self._run_callbacks(blocks)

    def _insert_first_block(self):
        resolver = self.initial_block_resolver or blocksel.ResolveGenesisBlock()
        block = resolver.resolve_block(self.w3)

        if not block:
            raise ValueError("Can't fetch initial block to sync from!")

        latest = self.w3.eth.getBlock("latest")
        safe_initial_blocknr = max(latest.number - self.max_reorg_depth, 0)
        if block.number > safe_initial_blocknr:
            unsafe_block = block
            block = self.w3.eth.getBlock(safe_initial_blocknr)
            self.logger.warn(
                f"choosing {format_block(block)} instead of {format_block(unsafe_block)}"
            )
        self.initial_blocknr = block.number

        self.logger.info(
            f"starting initial sync from {format_block(block)}, latest {format_block(latest)}"
        )
        self._insert_branch([block])

    def fetch_and_insert_new_blocks(
        self, *, max_number_of_blocks=5000, max_block_height: int = None
    ):
        """Fetches up to `max_number_of_blocks` blocks and only up to blocknumber `max_block_height` (inclusive)
        and updates the internal state
            If a full branch is fetched it also inserts the new blocks
            Returns the number of fetched blocks
        """
        if max_number_of_blocks < 1:
            return 0

        number_of_synced_blocks = 0

        if self.db.is_empty():
            self._insert_first_block()
            number_of_synced_blocks += 1

        # sync forwards at most up until the forward sync target, but no more than
        # max_number_of_blocks
        max_forward_block_height = (
            self.fetch_forward_sync_target()
            if max_block_height is None
            else min(self.fetch_forward_sync_target(), max_block_height)
        )
        max_forward_sync_blocks = max(0, max_number_of_blocks - number_of_synced_blocks)

        number_of_synced_blocks += self._sync_forwards(
            max_number_of_blocks=max_forward_sync_blocks,
            max_block_height=max_forward_block_height,
        )

        # sync backwards until we have synced max_number_of_blocks in total or we are fully synced
        assert 0 <= number_of_synced_blocks <= max_number_of_blocks
        max_backward_sync_blocks = max_number_of_blocks - number_of_synced_blocks

        number_of_synced_blocks += self._sync_backwards(
            max_number_of_blocks=max_backward_sync_blocks,
            max_block_height=max_block_height,
        )

        return number_of_synced_blocks

    def fetch_forward_sync_target(self):
        return max(self.w3.eth.blockNumber - self.max_reorg_depth, 0)

    def _sync_forwards(
        self, *, max_number_of_blocks: int, max_block_height: int
    ) -> int:
        block_numbers_to_fetch = range(
            self.head.number + 1,
            min(self.head.number + 1 + max_number_of_blocks, max_block_height + 1),
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

    def _sync_backwards(
        self, *, max_number_of_blocks: int, max_block_height: int = None
    ) -> int:
        branch_length_before = len(self.current_branch)
        complete = self._fetch_branch(
            max_number_of_blocks, blocknr_or_hash=max_block_height
        )
        number_of_fetched_blocks = len(self.current_branch) - branch_length_before

        if complete and len(self.current_branch) > 0:
            self._insert_branch(list(reversed(self.current_branch)))

        return number_of_fetched_blocks

    def _get_block(self, blocknr_or_hash):
        """call self.w3.eth.getBlock, but make sure we don't fetch a block
        before the initial block"""
        block = self.w3.eth.getBlock(blocknr_or_hash)
        assert block is not None, f"Could not fetch block {blocknr_or_hash}"

        if block.number < self.initial_blocknr:
            self.logger.error(
                f"Fetched block with number {block.number} < {self.initial_blocknr} (initial block number) on syncing backwards!"
            )
            raise FetchingForkWithUnkownBaseError(
                "Synchronized backwards on a fork with base before initial synchronized block!"
            )

        return block

    def _fetch_branch(self, max_blocks_to_fetch, blocknr_or_hash=None):

        if blocknr_or_hash is None:
            blocknr_or_hash = "latest"

        if max_blocks_to_fetch < 0:
            raise ValueError("Maximum number of blocks to fetch must be positive")
        elif max_blocks_to_fetch == 0:
            return False

        number_of_fetched_blocks = 0
        if len(self.current_branch) == 0:
            head = self._get_block(blocknr_or_hash)
            if self.db.contains(head.hash):
                self.logger.info(
                    "no new blocks",
                    head_hash=self.head.hash,
                    head_number=self.head.number,
                )
                return True

            self.current_branch = [head]
            number_of_fetched_blocks += 1

        while (
            not number_of_fetched_blocks >= max_blocks_to_fetch
            and not self.db.contains(self.current_branch[-1].parentHash)
        ):
            parent = self._get_block(self.current_branch[-1].parentHash)
            self.current_branch.append(parent)
            number_of_fetched_blocks += 1

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
