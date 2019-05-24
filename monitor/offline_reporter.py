from bisect import bisect_right
from collections import defaultdict
from typing import Any, NamedTuple, List, Callable, Set, Dict, DefaultDict

import structlog

from eth_utils import encode_hex

from monitor.validators import PrimaryOracle
from monitor.skip_reporter import SkippedProposal


class OfflineInterval(NamedTuple):
    step: int

    # length of the offline interval,
    # so length is the number of current validators
    length: int


class OfflineReporterStateV1(NamedTuple):
    reported_validators: Set[bytes]
    recent_skips_by_validator: Dict[bytes, Set[int]]


class OfflineReporterStateV2(NamedTuple):
    reported_validators: Set[bytes]
    recent_offline_intervals_by_validator: Dict[bytes, List[OfflineInterval]]

    # offline time in number of steps
    offline_time_by_validator: Dict[bytes, int]


def upgradeV1toV2(v1: OfflineReporterStateV1):
    return OfflineReporterStateV2(
        reported_validators=v1.reported_validators,
        recent_offline_intervals_by_validator={
            # Best we can do is to assume that they were at least 1 step offline
            validator: [OfflineInterval(step, 1) for step in recent_skips]
            for validator, recent_skips in v1.recent_skips_by_validator.items()
        },
        offline_time_by_validator={
            # assume offline for at least length of steps
            validator: len(recent_skips)
            for validator, recent_skips in v1.recent_skips_by_validator.items()
        },
    )


class OfflineReporter:
    """Report when validators are offline.

    The reporter expects to be notified whenever a validator has failed to propose during a step
    they were the primary of by calling it with the primary address and the skipped proposal.
    """

    logger = structlog.get_logger("monitor.offline_reporter")

    def __init__(
        self,
        state: OfflineReporterStateV2,
        primary_oracle: PrimaryOracle,
        offline_window_size,
        allowed_skip_rate,
    ):
        self.primary_oracle = primary_oracle

        self.offline_window_size = offline_window_size
        self.allowed_skip_rate = allowed_skip_rate

        self.reported_validators = state.reported_validators
        self.recent_offline_intervals_by_validator = defaultdict(
            list, state.recent_offline_intervals_by_validator
        )
        self.offline_time_by_validator = defaultdict(
            int, state.offline_time_by_validator
        )

        self.report_callbacks: List[Callable[[bytes, List[int]], Any]] = []

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @staticmethod
    def get_fresh_state():
        return OfflineReporterStateV2(
            reported_validators=set(),
            recent_offline_intervals_by_validator={},
            offline_time_by_validator={},
        )

    @property
    def state(self):
        return OfflineReporterStateV2(
            reported_validators=self.reported_validators,
            recent_offline_intervals_by_validator=dict(
                self.recent_offline_intervals_by_validator
            ),
            offline_time_by_validator=self.offline_time_by_validator,
        )

    def register_report_callback(self, callback):
        self.report_callbacks.append(callback)

    def __call__(self, primary, skipped_proposal: SkippedProposal):
        if primary in self.reported_validators:
            return  # ignore validators that have already been reported

        step = skipped_proposal.step

        self._clear_outdated_offline_intervals(step)
        self._update_offline_intervals(primary, skipped_proposal)

        if self._is_offline(primary):
            self.logger.info(
                "Detected offline validator", address=encode_hex(primary), step=step
            )

            self.reported_validators.add(primary)
            offline_steps = self.recent_offline_intervals_by_validator.pop(primary)

            for callback in self.report_callbacks:
                callback(
                    primary,
                    list(sorted(offline_step.step for offline_step in offline_steps)),
                )

    def _update_offline_intervals(
        self, validator: bytes, skipped_proposal: SkippedProposal
    ) -> None:
        # It is important that they are ordered
        if self.recent_offline_intervals_by_validator[validator]:
            assert (
                skipped_proposal.step
                > self.recent_offline_intervals_by_validator[validator][-1].step
            )
        length = len(self.primary_oracle.get_validators(skipped_proposal.block_height))

        self.recent_offline_intervals_by_validator[validator].append(
            OfflineInterval(skipped_proposal.step, length=length)
        )
        self.offline_time_by_validator[validator] += length

    def _clear_outdated_offline_intervals(self, current_step) -> None:
        cutoff = current_step - self.offline_window_size
        cleared_offline_steps_by_validator: DefaultDict[
            bytes, List[OfflineInterval]
        ] = defaultdict(list)

        for (
            validator,
            offline_steps,
        ) in self.recent_offline_intervals_by_validator.items():
            # OfflineStep(cutoff, 0) is used because bisect does not support a key
            index = bisect_right(offline_steps, OfflineInterval(cutoff, 0))
            cleared_offline_steps_by_validator[validator] = offline_steps[index:]

            for offline_step in offline_steps[:index]:
                self.offline_time_by_validator[validator] -= offline_step.length

        self.recent_offline_intervals_by_validator = cleared_offline_steps_by_validator

    def _is_offline(self, validator: bytes) -> bool:
        skip_rate = self.offline_time_by_validator[validator] / self.offline_window_size
        return skip_rate > self.allowed_skip_rate
