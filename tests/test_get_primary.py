import pytest

from monitor.validators import (
    validate_validator_definition,
    validate_validator_definition_order,
    ValidatorDefinitionRange,
    get_validator_definition_ranges,
)


@pytest.mark.parametrize(
    "invalid_validator_definition",
    [
        None,
        "0x" + "00" * 20,
        ["0x" + "00" * 20],
        {},
        {"0": ["0x" + "00" * 20]},
        {"list": []},
        {"multi": None},
        {"multi": []},
        {"multi": {}},
        {"multi": {"100": None}},
        {"multi": {"0": []}},
        {"multi": {"0": {}}},
        {"multi": {"0": None}},
        {"multi": {"foo": None, "0": None}},
        {"multi": {"0": ["0x" + "00" * 20]}},
        {"multi": {"0": {"foo": None}}},
        {"multi": {"0": {"list": None}}},
        {"multi": {"0": {"list": []}}},
        {"multi": {"0": {"list": {}}}},
        {"multi": {"0": {"list": ["foo"]}}},
        {"multi": {"0": {"list": ["0x" + "gg" * 20]}}},
        {"multi": {"0": {"list": [b"\x00" * 20]}}},
        {"multi": {"1": {"list": ["0x" + "00" * 20]}}},
        {"multi": {0: {"list": ["0x" + "00" * 20]}}},
        {"multi": {"0": {"list": ["0x" + "00" * 20]}, "another_key": []}},
        {"multi": {"0": {"list": ["0x" + "00" * 20], "another_key": []}}},
        {"multi": {"0": {"contract": None}}},
        {"multi": {"0": {"contract": "foo"}}},
        {"multi": {"0": {"contract": "0x" + "gg" * 20}}},
        {"multi": {"0": {"contract": b"\x00" * 20}}},
        {"multi": {"0": {"safeContract": None}}},
        {"multi": {"0": {"safeContract": "foo"}}},
        {"multi": {"0": {"safeContract": "0x" + "gg" * 20}}},
        {"multi": {"0": {"safeContract": b"\x00" * 20}}},
    ],
)
def test_validation_invalid(invalid_validator_definition):
    with pytest.raises(ValueError):
        validate_validator_definition(invalid_validator_definition)


# Reusable definition
validator_definition = {
    "multi": {
        "0": {"list": ["0x" + "00" * 20, "0x" + "11" * 20]},
        "100": {"contract": "0x" + "00" * 20},
        "300": {"list": ["0x" + "22" * 20, "0x" + "33" * 20]},
        "200": {"safeContract": "0x" + "11" * 20},
    }
}


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
        validator_definition,
    ],
)
def test_validation_valid(valid_validator_definition):
    validate_validator_definition(valid_validator_definition)


def test_get_ranges():
    ranges = get_validator_definition_ranges(validator_definition)
    assert ranges == [
        ValidatorDefinitionRange(
            leave_height="100",
            enter_height="0",
            is_contract=False,
            validators=[
                "0x0000000000000000000000000000000000000000",
                "0x1111111111111111111111111111111111111111",
            ],
        ),
        ValidatorDefinitionRange(
            leave_height="200",
            enter_height="100",
            is_contract=True,
            contract_address="0x0000000000000000000000000000000000000000",
        ),
        ValidatorDefinitionRange(
            leave_height="300",
            enter_height="200",
            is_contract=True,
            contract_address="0x1111111111111111111111111111111111111111",
        ),
        ValidatorDefinitionRange(
            leave_height=None,
            enter_height="300",
            is_contract=False,
            validators=[
                "0x2222222222222222222222222222222222222222",
                "0x3333333333333333333333333333333333333333",
            ],
        ),
    ]


def test_validate_valid_range_order():
    validate_validator_definition_order(
        [
            ValidatorDefinitionRange(
                enter_height=100,
                leave_height=200,
                is_contract=True,
                contract_address=b"\x00" * 20,
            ),
            ValidatorDefinitionRange(
                enter_height=200,
                leave_height=None,
                is_contract=True,
                contract_address=b"\x00" * 20,
            ),
        ]
    )


def test_validate_valid_ranges():
    with pytest.raises(ValueError):
        validate_validator_definition_order(
            [
                ValidatorDefinitionRange(
                    enter_height=100,
                    leave_height=200,
                    is_contract=True,
                    contract_address=b"\x00" * 20,
                ),
                ValidatorDefinitionRange(
                    enter_height=201,
                    leave_height=None,
                    is_contract=True,
                    contract_address=b"\x00" * 20,
                ),
            ]
        )
