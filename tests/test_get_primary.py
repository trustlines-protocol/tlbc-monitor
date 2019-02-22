import pytest

from monitor.validators import (
    validate_validator_definition,
    make_primary_function,
)


@pytest.mark.parametrize("invalid_validator_definition", [
    "0x" + "00" * 20,
    ["0x" + "00" * 20],
    {},
    {"0": ["0x" + "00" * 20]},
    {"multi": []},
    {"multi": {}},
    {"multi": {"0": []}},
    {"multi": {"0": ["0x" + "00" * 20]}},
    {"multi": {"0": {"list": []}}},
    {"multi": {"0": {"list": {}}}},
    {"multi": {"0": {"list": ["0x" + "gg" * 20]}}},
    {"multi": {"0": {"list": [b"\x00" * 20]}}},
    {"multi": {"0": {"contract": "0x0000000000000000000000000000000000000005"}}},
    {"multi": {"1": {"list": ["0x" + "00" * 20]}}},
    {"multi": {0: {"list": ["0x" + "00" * 20]}}},
    {"multi": {"0": {"list": ["0x" + "00" * 20]}, "another_key": []}},
    {"multi": {"0": {"list": ["0x" + "00" * 20], "another_key": []}}},
])
def test_validation_invalid(invalid_validator_definition):
    with pytest.raises(ValueError):
        validate_validator_definition(invalid_validator_definition)


@pytest.mark.parametrize("valid_validator_definition", [
    {"multi": {"0": {"list": ["0x" + "00" * 20]}}},
    {"multi": {"0": {"list": ["0x" + "00" * 20, "0x" + "11" * 20]}}},
    {"multi": {"0": {"list": ["0x" + "00" * 20]}, "100": {"list": ["0x" + "11" * 20]}}},
])
def test_validation_valid(valid_validator_definition):
    validate_validator_definition(valid_validator_definition)


@pytest.mark.parametrize("validator_definition, slots, primaries", [
    (
        {"multi": {"0": {"list": ["0x" + "00" * 20]}}},
        [0, 1, 2, 3, 4, 5, 1000],
        [b"\x00" * 20],
    ),
    (
        {"multi": {"0": {"list": ["0x" + "00" * 20]}, "5": {"list": ["0x" + "11" * 20]}}},
        [0, 1, 4, 5, 6, 1000],
        [b"\x00" * 20] * 3 + [b"\x11" * 20] * 3,
    ),
    (
        {"multi": {"0": {"list": ["0x" + "00" * 20, "0x" + "11" * 20]}}},
        [0, 1, 2, 3, 1000, 1001],
        [b"\x00" * 20, b"\x11" * 20] * 3,
    ),
    (
        {"multi": {
            "0": {"list": ["0x" + "00" * 20]},
            "3": {"list": ["0x" + "11" * 20, "0x" + "22" * 20]},
        }},
        [3, 4, 5, 6, 1001, 1002],
        [b"\x22" * 20, b"\x11" * 20] * 3,
    ),
])
def test_get_primary_for_slot(validator_definition, slots, primaries):
    get_primary_for_slot = make_primary_function(validator_definition)
    for slot, primary in zip(slots, primaries):
        assert get_primary_for_slot(slot) == primary
