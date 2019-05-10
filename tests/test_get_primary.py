import pytest

from monitor.validators import validate_validator_definition


@pytest.mark.parametrize(
    "invalid_validator_definition",
    [
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
    ],
)
def test_validation_invalid(invalid_validator_definition):
    with pytest.raises(ValueError):
        validate_validator_definition(invalid_validator_definition)


@pytest.mark.parametrize(
    "valid_validator_definition",
    [
        {"multi": {"0": {"list": ["0x" + "00" * 20]}}},
        {"multi": {"0": {"list": ["0x" + "00" * 20, "0x" + "11" * 20]}}},
        {
            "multi": {
                "0": {"list": ["0x" + "00" * 20]},
                "100": {"list": ["0x" + "11" * 20]},
            }
        },
    ],
)
def test_validation_valid(valid_validator_definition):
    validate_validator_definition(valid_validator_definition)
