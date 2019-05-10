import pytest

from monitor.validators import PrimaryOracle, Epoch


VAL1 = b"\x00" * 20
VAL2 = b"\x01" * 20
VAL3 = b"\x02" * 20
VAL4 = b"\x03" * 20


def test_get_primary_single_epoch():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(0, [VAL1, VAL2]))
    for height in range(10):
        for step in range(0, 10, 2):
            assert primary_oracle.get_primary(height, step) == VAL1
        for step in range(1, 10, 2):
            assert primary_oracle.get_primary(height, step) == VAL2


def test_get_primary_two_epochs():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(0, [VAL1, VAL2]))
    primary_oracle.add_epoch(Epoch(5, [VAL3, VAL4]))
    for height in range(5):
        for step in range(0, 10, 2):
            assert primary_oracle.get_primary(height, step) == VAL1
        for step in range(1, 10, 2):
            assert primary_oracle.get_primary(height, step) == VAL2
    for height in range(5, 10):
        for step in range(0, 10, 2):
            assert primary_oracle.get_primary(height, step) == VAL3
        for step in range(1, 10, 2):
            assert primary_oracle.get_primary(height, step) == VAL4


def test_get_primary_no_epochs():
    primary_oracle = PrimaryOracle()
    for height in range(5):
        for step in range(10):
            with pytest.raises(ValueError):
                primary_oracle.get_primary(height, step)


def test_get_primary_late_epoch():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(5, [VAL1]))
    for height in range(5):
        for step in range(10):
            with pytest.raises(ValueError):
                primary_oracle.get_primary(height, step)


def test_add_empty_epoch():
    primary_oracle = PrimaryOracle()
    with pytest.raises(ValueError):
        primary_oracle.add_epoch(Epoch(0, []))


def test_epoch_sorting():
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(Epoch(0, [VAL1]))
    primary_oracle.add_epoch(Epoch(10, [VAL3]))
    primary_oracle.add_epoch(Epoch(5, [VAL2]))
    for height in range(5):
        assert primary_oracle.get_primary(height, 0) == VAL1
    for height in range(5, 10):
        assert primary_oracle.get_primary(height, 0) == VAL2
    for height in range(10, 15):
        assert primary_oracle.get_primary(height, 0) == VAL3
