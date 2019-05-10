import pytest

import itertools

from unittest.mock import Mock

from monitor.offline_reporter import OfflineReporter


OFFLINE_WINDOW_SIZE = 20
ALLOWED_SKIP_RATE = 0.5


@pytest.fixture
def assigned_steps(primary_oracle):
    def f(validator):
        return (
            step
            for step in itertools.count()
            if primary_oracle.get_primary(height=0, step=step) == validator
        )

    return f


@pytest.fixture
def offline_reporter(validators, primary_oracle):
    return OfflineReporter.from_fresh_state(
        primary_oracle=primary_oracle,
        offline_window_size=OFFLINE_WINDOW_SIZE,
        allowed_skip_rate=ALLOWED_SKIP_RATE,
    )


def test_report_entirely_offline_validator(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    offline_validator = validators[0]
    for step in [0, 3, 6, 9]:
        offline_reporter(offline_validator, step)

    report_callback.assert_called_once_with(offline_validator, [0, 3, 6, 9])


def test_barely_offline_validator(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    offline_validator = validators[0]
    for step in [0, 6, 12, 18]:
        offline_reporter(offline_validator, step)

    report_callback.assert_called_once_with(offline_validator, [0, 6, 12, 18])


def test_minimally_proposing_validator(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    validator = validators[0]
    for step in [0, 6, 12, 21, 27]:
        offline_reporter(validator, step)

    report_callback.assert_not_called()


def test_bursts_below_threshold(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    validator = validators[0]
    for step in [0, 3, 6, 21, 24, 27, 42, 45, 48]:
        offline_reporter(validator, step)

    report_callback.assert_not_called()


def test_no_repeated_reporting(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    offline_validator = validators[0]
    for step in range(0, 100, 3):
        offline_reporter(offline_validator, step)

    report_callback.assert_called_once()


def test_multiple_offline_validators(validators, offline_reporter, primary_oracle):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    for step in [0, 1, 3, 4, 6, 7]:
        offline_reporter(primary_oracle.get_primary(height=0, step=step), step)

    offline_reporter(validators[0], 9)
    report_callback.assert_called_once_with(validators[0], [0, 3, 6, 9])
    report_callback.reset_mock()

    offline_reporter(validators[1], 10)
    report_callback.assert_called_once_with(validators[1], [1, 4, 7, 10])
    report_callback.reset_mock()


def test_reporting_after_restart(validators, offline_reporter, primary_oracle):
    for step in [0, 1, 3, 4, 6, 7]:
        offline_reporter(primary_oracle.get_primary(height=0, step=step), step)
    offline_reporter(validators[0], 9)

    restarted_offline_reporter = OfflineReporter(
        state=offline_reporter.state,
        primary_oracle=primary_oracle,
        offline_window_size=OFFLINE_WINDOW_SIZE,
        allowed_skip_rate=ALLOWED_SKIP_RATE,
    )
    report_callback = Mock()
    restarted_offline_reporter.register_report_callback(report_callback)

    restarted_offline_reporter(validators[1], 10)
    report_callback.assert_called_once_with(validators[1], [1, 4, 7, 10])
    report_callback.reset_mock()

    restarted_offline_reporter(validators[0], 12)
    report_callback.assert_not_called()
