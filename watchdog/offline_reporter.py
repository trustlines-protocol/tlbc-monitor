from collections import (
    defaultdict,
)
from fractions import Fraction
from typing import (
    Any,
    NamedTuple,
)

import structlog

from eth_utils import (
    encode_hex,
)


class OfflineReporterStateV1(NamedTuple):
    reported_validators: Any
    recent_skips_by_validator: Any


class OfflineReporter:
    """Report when validators are offline.

    The reporter expects to be notified whenever a validator has failed to propose during a step
    they were the primary of by calling it with the primary address and step number.
    """

    logger = structlog.get_logger("watchdog.offline_reporter")

    def __init__(self, state, get_primary_for_step, offline_window_size, allowed_skip_rate):
        self.get_primary_for_step = get_primary_for_step

        self.offline_window_size = offline_window_size
        self.allowed_skip_rate = allowed_skip_rate

        self.reported_validators = state.reported_validators
        self.recent_skips_by_validator = defaultdict(set, state.recent_skips_by_validator)

        self.report_callbacks = []

    @classmethod
    def from_fresh_state(cls, *args, **kwargs):
        return cls(cls.get_fresh_state(), *args, **kwargs)

    @classmethod
    def get_fresh_state(cls):
        return OfflineReporterStateV1(
            reported_validators=set(),
            recent_skips_by_validator={}
        )

    @property
    def state(self):
        return OfflineReporterStateV1(
            reported_validators=self.reported_validators,
            recent_skips_by_validator=dict(self.recent_skips_by_validator)
        )

    def register_report_callback(self, callback):
        self.report_callbacks.append(callback)

    def __call__(self, primary, step):
        if primary in self.reported_validators:
            return  # ignore validators that have already been reported

        self._clear_old_skips(step)
        self.recent_skips_by_validator[primary].add(step)

        if self._is_offline(primary, self.recent_skips_by_validator[primary], step):
            self.logger.info(
                "Detected offline validator",
                address=encode_hex(primary),
                step=step,
            )

            self.reported_validators.add(primary)
            skips = self.recent_skips_by_validator.pop(primary)

            for callback in self.report_callbacks:
                callback(primary, list(sorted(skips)))

    def _clear_old_skips(self, current_step):
        cutoff = current_step - self.offline_window_size
        self.recent_skips_by_validator = defaultdict(set, {
            validator: {step for step in skips if step >= cutoff}
            for validator, skips in self.recent_skips_by_validator.items()
        })

    def _is_offline(self, validator, skips, current_step):
        window = range(
            current_step - self.offline_window_size + 1,
            current_step + 1,
        )

        assigned_steps = [
            step for step in window
            if self.get_primary_for_step(step) == validator
        ]
        missed_steps_in_window = [
            step for step in skips
            if step in window
        ]

        skip_rate = Fraction(len(missed_steps_in_window), len(assigned_steps))
        return skip_rate > self.allowed_skip_rate
