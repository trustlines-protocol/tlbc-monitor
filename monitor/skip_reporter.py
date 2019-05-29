from typing import Any, NamedTuple, List, Callable, Set

import structlog

from eth_utils import encode_hex

from monitor.validators import PrimaryOracle


class SkipReporterStateV1(NamedTuple):
    latest_step: int
    open_steps: Set[int]


# We have to keep the not versioned name for backwards compatibility because we use pickle
SkipReporterState = SkipReporterStateV1


class SkipReporterStateV2(NamedTuple):
    latest_step: int
    open_skipped_proposals: Set["SkippedProposal"]


def upgrade_v1_to_v2(v1: SkipReporterStateV1):
    # As we can not recover the block height, we will just clear the proposels
    return SkipReporterStateV2(latest_step=v1.latest_step, open_skipped_proposals=set())


class SkippedProposal(NamedTuple):
    step: int
    block_height: int


class SkipReporter:
    """Report whenever validators do not propose in time.

    This reporter expects to be notified for each new block by calling it with the block in the
    format returned by web3.py.
    """

    logger = structlog.get_logger("monitor.skip_reporter")

    def __init__(
        self, state, primary_oracle: PrimaryOracle, grace_period: int = 20
    ) -> None:
        self.primary_oracle = primary_oracle
        self.grace_period = grace_period

        self.latest_step = state.latest_step
        self.open_skipped_proposals = state.open_skipped_proposals
        self.report_callbacks: List[Callable[[bytes, int], Any]] = []

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @staticmethod
    def get_fresh_state():
        return SkipReporterStateV2(latest_step=0, open_skipped_proposals=set())

    @property
    def state(self):
        return SkipReporterStateV2(
            latest_step=self.latest_step,
            open_skipped_proposals=self.open_skipped_proposals,
        )

    def register_report_callback(self, callback):
        self.report_callbacks.append(callback)

    def __call__(self, block):
        block_step = int(block.step)
        block_height = int(block.number)

        if block_height == 0:
            # We don't want to report skips between genesis and the first block as genesis always has step 0
            # so we ignore the genesis block
            return

        if self.latest_step == 0:
            self.latest_step = block_step
            self.logger.debug("received first block", step=self.latest_step)
            return

        self.update_open_skipped_proposals(block_step, block_height)
        self.remove_open_skipped_proposals_with_step(block_step)

        # report misses
        missed_proposals = self.get_missed_proposals()

        reported_proposals = set()
        for proposal in missed_proposals:
            primary = self.primary_oracle.get_primary(
                height=proposal.block_height, step=proposal.step
            )
            self.logger.info(
                "detected missed step", primary=encode_hex(primary), step=proposal.step
            )
            for callback in self.report_callbacks:
                callback(primary, proposal)

            reported_proposals.add(proposal)

        # remove misses from open steps as they have been reported already
        self.open_skipped_proposals -= set(reported_proposals)

    def update_open_skipped_proposals(self, step_seen, block_height_seen):
        if step_seen > self.latest_step:
            for step in range(self.latest_step + 1, step_seen):
                skipped_proposal = SkippedProposal(step, block_height_seen)
                self.open_skipped_proposals.add(skipped_proposal)
            self.latest_step = step_seen

    def remove_open_skipped_proposals_with_step(self, step):

        self.open_skipped_proposals = {
            proposal
            for proposal in self.open_skipped_proposals
            if proposal.step != step
        }

    def get_missed_proposals(self):
        grace_period_end = self.latest_step - self.grace_period
        missed_skips = [
            skipped_proposal
            for skipped_proposal in self.open_skipped_proposals
            if skipped_proposal.step < grace_period_end
        ]
        missed_skips = sorted(missed_skips, key=lambda x: x.step)
        return missed_skips
