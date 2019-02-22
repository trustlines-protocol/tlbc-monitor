from typing import (
    Any,
    NamedTuple,
)

import structlog

from eth_utils import (
    encode_hex,
)


class SkipReporterState(NamedTuple):
    latest_step: Any
    open_steps: Any


class SkipReporter:
    """Report whenever validators do not propose in time.

    This reporter expects to be notified for each new block by calling it with the block in the
    format returned by web3.py.
    """

    logger = structlog.get_logger("watchdog.skip_reporter")

    def __init__(self, state, get_primary_for_step, grace_period=20):
        self.get_primary_for_step = get_primary_for_step
        self.grace_period = grace_period

        self.latest_step = state.latest_step
        self.open_steps = state.open_steps

        self.report_callbacks = []

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @staticmethod
    def get_fresh_state():
        return SkipReporterState(
            latest_step=None,
            open_steps=set(),
        )

    @property
    def state(self):
        return SkipReporterState(
            latest_step=self.latest_step,
            open_steps=self.open_steps,
        )

    def register_report_callback(self, callback):
        self.report_callbacks.append(callback)

    def __call__(self, block):
        block_step = int(block.step)

        # don't report skips between genesis and the first block as genesis always has step 0
        if self.latest_step is None:
            self.latest_step = block_step
            self.logger.info("received first block", step=self.latest_step)
            return

        self.update_open_steps(block_step)

        # remove block step from open step list
        self.open_steps.discard(block_step)

        # report misses
        missed_steps = self.get_missed_steps()
        for step in missed_steps:
            primary = self.get_primary_for_step(step)
            self.logger.info(
                "detected missed step",
                primary=encode_hex(primary),
                step=step,
            )
            for callback in self.report_callbacks:
                callback(primary, step)

        # remove misses from open steps as they have been reported already
        self.open_steps -= set(missed_steps)

    def update_open_steps(self, current_step):
        if current_step > self.latest_step:
            self.open_steps |= set(range(self.latest_step + 1, current_step + 1))
            self.latest_step = current_step

    def get_missed_steps(self):
        grace_period_end = self.latest_step - self.grace_period
        missed_steps = sorted([step for step in self.open_steps if step < grace_period_end])
        return missed_steps
