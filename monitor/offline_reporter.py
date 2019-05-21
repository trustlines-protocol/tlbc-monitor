from collections import defaultdict
from fractions import Fraction
from typing import Any, NamedTuple, List, Callable

import structlog

from eth_utils import encode_hex

from monitor.validators import PrimaryOracle
from monitor.skip_reporter import SkippedProposal


class OfflineReporterStateV1(NamedTuple):
    missed_steps: Any
    reported_validators: Any
    recent_skips_by_validator: Any


class OfflineReporter:
    """Report when validators are offline.

    The reporter expects to be notified whenever a validator has failed to propose during a step
    they were the primary of by calling it with the primary address and step number.
    """

    logger = structlog.get_logger("monitor.offline_reporter")

    def __init__(
        self,
        state: OfflineReporterStateV1,
        primary_oracle: PrimaryOracle,
        offline_window_size,
        allowed_skip_rate,
    ):
        self.primary_oracle = primary_oracle

        self.offline_window_size = offline_window_size
        self.allowed_skip_rate = allowed_skip_rate

        self.missed_steps = state.missed_steps
        self.reported_validators = state.reported_validators
        self.recent_skips_by_validator = defaultdict(
            set, state.recent_skips_by_validator
        )

        self.report_callbacks: List[Callable[[bytes, List[int]], Any]] = []

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @staticmethod
    def get_fresh_state():
        return OfflineReporterStateV1(
            missed_steps=set(),
            reported_validators=set(),
            recent_skips_by_validator={},
        )

    @property
    def state(self):
        return OfflineReporterStateV1(
            missed_steps=self.missed_steps,
            reported_validators=self.reported_validators,
            recent_skips_by_validator=dict(self.recent_skips_by_validator),
        )

    def register_report_callback(self, callback):
        self.report_callbacks.append(callback)

    def __call__(self, primary, skipped_proposal: SkippedProposal):
        if primary in self.reported_validators:
            return  # ignore validators that have already been reported

        step = skipped_proposal.step

        self.missed_steps.add(step)
        self.missed_steps.discard(step - self.offline_window_size)  # TODO: discard more than this?

        self._clear_old_skips(step)
        self.recent_skips_by_validator[primary].add(step)

        if self._is_offline(primary, self.recent_skips_by_validator[primary], skipped_proposal):
            self.logger.info(
                "Detected offline validator", address=encode_hex(primary), step=step
            )

            self.reported_validators.add(primary)
            skips = self.recent_skips_by_validator.pop(primary)

            for callback in self.report_callbacks:
                callback(primary, list(sorted(skips)))

    def _clear_old_skips(self, current_step):
        cutoff = current_step - self.offline_window_size
        self.recent_skips_by_validator = defaultdict(
            set,
            {
                validator: {step for step in skips if step >= cutoff}
                for validator, skips in self.recent_skips_by_validator.items()
            },
        )

    def _is_offline(self, validator, recent_skipped_proposals, skipped_proposal):

        assigned_steps = self._get_assigned_steps_in_offline_window(validator, skipped_proposal)

        current_step = skipped_proposal.step
        window = range(current_step - self.offline_window_size + 1, current_step + 1)

        missed_steps_in_window = [step for step in recent_skipped_proposals if step in window]

        skip_rate = Fraction(len(missed_steps_in_window), assigned_steps)
        return skip_rate > self.allowed_skip_rate

    def _get_assigned_steps_in_offline_window(self, validator, skipped_proposal: SkippedProposal):
        current_step = skipped_proposal.step
        block_height_of_step = skipped_proposal.block_height

        window = range(current_step - self.offline_window_size + 1, current_step + 1)
        reversed_window = reversed(window)

        assigned_steps = 0
        for step in reversed_window:
            if self.primary_oracle.get_primary(height=block_height_of_step, step=step) == validator:
                assigned_steps += 1
            if step not in self.missed_steps:
                block_height_of_step -= 1

        return assigned_steps
