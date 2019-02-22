import pytest

import itertools

from unittest.mock import Mock

from monitor.offline_reporter import (
    OfflineReporter,
)


OFFLINE_WINDOW_SIZE = 20
ALLOWED_SKIP_RATE = 0.5


@pytest.fixture
def validators():
    return [
        b"\x00" * 20,
        b"\x11" * 20,
        b"\x22" * 20,
    ]


@pytest.fixture
def get_primary_for_step(validators):

    def f(step):
        return validators[step % len(validators)]

    return f


@pytest.fixture
def assigned_steps(get_primary_for_step):

    def f(validator):
        return (
            step for step in itertools.count()
            if get_primary_for_step(step) == validator
        )

    return f


@pytest.fixture
def offline_reporter(validators, get_primary_for_step):
    return OfflineReporter.from_fresh_state(
        get_primary_for_step=get_primary_for_step,
        offline_window_size=OFFLINE_WINDOW_SIZE,
        allowed_skip_rate=ALLOWED_SKIP_RATE,
    )


def test_report_entirely_offline_validator(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    offline_validator = validators[0]
    for step in [0, 3, 6, 9]:
        offline_reporter(offline_validator, step)

    report_callback.assert_called_once_with(
        offline_validator,
        [0, 3, 6, 9],
    )


def test_barely_offline_validator(validators, offline_reporter):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    offline_validator = validators[0]
    for step in [0, 6, 12, 18]:
        offline_reporter(offline_validator, step)

    report_callback.assert_called_once_with(
        offline_validator,
        [0, 6, 12, 18],
    )


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


def test_multiple_offline_validators(validators, offline_reporter, get_primary_for_step):
    report_callback = Mock()
    offline_reporter.register_report_callback(report_callback)

    for step in [0, 1, 3, 4, 6, 7]:
        offline_reporter(get_primary_for_step(step), step)

    offline_reporter(validators[0], 9)
    report_callback.assert_called_once_with(validators[0], [0, 3, 6, 9])
    report_callback.reset_mock()

    offline_reporter(validators[1], 10)
    report_callback.assert_called_once_with(validators[1], [1, 4, 7, 10])
    report_callback.reset_mock()


def test_reporting_after_restart(validators, offline_reporter, get_primary_for_step):
    for step in [0, 1, 3, 4, 6, 7]:
        offline_reporter(get_primary_for_step(step), step)
    offline_reporter(validators[0], 9)

    restarted_offline_reporter = OfflineReporter(
        state=offline_reporter.state,
        get_primary_for_step=get_primary_for_step,
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
