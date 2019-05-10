import pytest

from monitor.validators import PrimaryOracle, Epoch


VALIDATOR1 = b"\x00" * 20
VALIDATOR2 = b"\x01" * 20
VALIDATOR3 = b"\x02" * 20
VALIDATOR4 = b"\x03" * 20


def test_get_primary_single_epoch():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(0, [VALIDATOR1, VALIDATOR2]))
    for height in range(10):
        for step in range(0, 10, 2):
            assert primary_oracle.get_primary(height=height, step=step) == VALIDATOR1
        for step in range(1, 10, 2):
            assert primary_oracle.get_primary(height=height, step=step) == VALIDATOR2


def test_get_primary_two_epochs():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(0, [VALIDATOR1, VALIDATOR2]))
    primary_oracle.add_epoch(Epoch(5, [VALIDATOR3, VALIDATOR4]))
    for height in range(5):
        for step in range(0, 10, 2):
            assert primary_oracle.get_primary(height=height, step=step) == VALIDATOR1
        for step in range(1, 10, 2):
            assert primary_oracle.get_primary(height=height, step=step) == VALIDATOR2
    for height in range(5, 10):
        for step in range(0, 10, 2):
            assert primary_oracle.get_primary(height=height, step=step) == VALIDATOR3
        for step in range(1, 10, 2):
            assert primary_oracle.get_primary(height=height, step=step) == VALIDATOR4


def test_get_primary_no_epochs():
    primary_oracle = PrimaryOracle()
    for height in range(5):
        for step in range(10):
            with pytest.raises(ValueError):
                primary_oracle.get_primary(height=height, step=step)


def test_get_primary_late_epoch():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(5, [VALIDATOR1]))
    for height in range(5):
        for step in range(10):
            with pytest.raises(ValueError):
                primary_oracle.get_primary(height=height, step=step)


def test_add_empty_epoch():
    primary_oracle = PrimaryOracle()
    with pytest.raises(ValueError):
        primary_oracle.add_epoch(Epoch(0, []))


def test_epoch_sorting():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(0, [VALIDATOR1]))
    primary_oracle.add_epoch(Epoch(10, [VALIDATOR3]))
    primary_oracle.add_epoch(Epoch(5, [VALIDATOR2]))
    for height in range(5):
        assert primary_oracle.get_primary(height=height, step=0) == VALIDATOR1
    for height in range(5, 10):
        assert primary_oracle.get_primary(height=height, step=0) == VALIDATOR2
    for height in range(10, 15):
        assert primary_oracle.get_primary(height=height, step=0) == VALIDATOR3
