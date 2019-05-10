from monitor.validators import ValidatorDefinitionRange, Epoch, get_static_epochs


VALIDATOR1 = b"\x00" * 20
VALIDATOR2 = b"\x01" * 20
CONTRACT_ADDRESS = b"\xff" * 20


def test_get_static_epochs():
    ranges = [
        ValidatorDefinitionRange(
            transition_to_height=0,
            transition_from_height=5,
            is_contract=False,
            contract_address=None,
            validators=[VALIDATOR1],
        ),
        ValidatorDefinitionRange(
            transition_to_height=5,
            transition_from_height=10,
            is_contract=True,
            contract_address=CONTRACT_ADDRESS,
            validators=None,
        ),
        ValidatorDefinitionRange(
            transition_to_height=10,
            transition_from_height=None,
            is_contract=False,
            contract_address=None,
            validators=[VALIDATOR2],
        ),
    ]
    epochs = get_static_epochs(ranges)
    assert epochs == [Epoch(0, [VALIDATOR1]), Epoch(10, [VALIDATOR2])]
