import pytest
from unittest.mock import Mock, call

from web3.datastructures import AttributeDict

from monitor.skip_reporter import SkipReporter, SkippedProposal


@pytest.fixture
def report_callback():
    return Mock()


def mock_block(step, number):
    return AttributeDict({"step": str(step), "number": number})


def test_no_skips(report_callback, primary_oracle):
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=5,
    )
    skip_reporter.register_report_callback(report_callback)

    for step in range(1, 100):
        skip_reporter(mock_block(step, number=step))
    report_callback.assert_not_called()


def test_do_not_report_skips_after_genesis(report_callback, primary_oracle):
    # The genesis is always 0, so we do not want to report misses right after genesis
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=5,
    )
    skip_reporter.register_report_callback(report_callback)

    for step in [0, 10, 11]:
        skip_reporter(mock_block(step, number=step))
    report_callback.assert_not_called()


def test_validator_offline(primary_oracle, report_callback, validators):
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=3,
    )
    skip_reporter.register_report_callback(report_callback)
    number = 1
    for step in range(1, 11):
        if primary_oracle.get_primary(height=0, step=step) != validators[0]:
            skip_reporter(mock_block(step, number=number))
            number += 1

    assert report_callback.call_args_list == [
        call(validators[0], SkippedProposal(step=3, block_height=3)),
        call(validators[0], SkippedProposal(step=6, block_height=5)),
    ]


def test_single_skip(primary_oracle, report_callback):
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=5,
    )
    skip_reporter.register_report_callback(report_callback)

    # normal mode
    for step in range(1, 21):
        skip_reporter(mock_block(step, number=step))

    # step 21 is skipped

    # single skip should not be reported during grace period
    for step in range(22, 27):
        skip_reporter(mock_block(step, number=step - 1))
        report_callback.assert_not_called()

    # skip is reported after grace period is over
    skip_reporter(mock_block(27, 26))
    report_callback.assert_called_once_with(
        primary_oracle.get_primary(height=21, step=21), SkippedProposal(21, 21)
    )
    report_callback.reset_mock()

    # skip is not reported again
    for step in range(28, 100):
        skip_reporter(mock_block(step, step - 1))
    report_callback.assert_not_called()


def test_skip_recovery(primary_oracle, report_callback):
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=5,
    )
    skip_reporter.register_report_callback(report_callback)

    # normal until step 2
    for step in range(1, 3):
        skip_reporter(mock_block(step, number=step))

    # validator 0 skips step 3

    # normal until step 3 + grace_period
    for step in range(4, 8):
        skip_reporter(mock_block(step, number=step - 1))

    # late proposal
    skip_reporter(mock_block(3, number=3))

    report_callback.assert_not_called()

    # normal from then on
    for step in range(4, 100):
        skip_reporter(mock_block(step, number=step))

    report_callback.assert_not_called()


def test_report_after_restart(primary_oracle, report_callback):
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=5,
    )

    # online at 1
    skip_reporter(mock_block(1, number=1))

    # offline at step 2

    # online from step 3 to 4
    for step in range(3, 5):
        skip_reporter(mock_block(step, number=step - 1))

    # restart
    restarted_skip_reporter = SkipReporter(
        state=skip_reporter.state, primary_oracle=primary_oracle, grace_period=5
    )
    restarted_skip_reporter.register_report_callback(report_callback)

    # no reports in steps 5 to 7
    for step in range(5, 8):
        restarted_skip_reporter(mock_block(step, number=step - 1))
        report_callback.assert_not_called()

    # report at step 8
    restarted_skip_reporter(mock_block(8, number=7))
    report_callback.assert_called_once_with(
        primary_oracle.get_primary(height=2, step=2),
        SkippedProposal(step=2, block_height=2),
    )


def test_no_repeated_report_after_restart(primary_oracle, report_callback):
    skip_reporter = SkipReporter(
        state=SkipReporter.get_fresh_state(),
        primary_oracle=primary_oracle,
        grace_period=5,
    )

    # mine some blocks
    for step in range(1, 21):
        skip_reporter(mock_block(step, number=step))

    # step 21 is skipped

    # mine until report
    for step in range(22, 28):
        skip_reporter(mock_block(step, number=step - 1))

    # restart, mine blocks, and check that no additional report is created
    restarted_skip_reporter = SkipReporter(
        state=skip_reporter.state, primary_oracle=primary_oracle, grace_period=5
    )
    skip_reporter.register_report_callback(report_callback)
    for step in range(28, 100):
        restarted_skip_reporter(mock_block(step, number=step - 1))
    report_callback.assert_not_called()
