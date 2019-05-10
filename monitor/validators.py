from collections.abc import Mapping
from itertools import tee, islice, chain
from typing import NamedTuple, List, Optional

from eth_utils import is_hex_address, to_canonical_address


def validate_validator_definition(validator_definition):
    if not isinstance(validator_definition, Mapping):
        raise ValueError("Validator definition must be a mapping")

    if list(validator_definition.keys()) != ["multi"]:
        raise ValueError("Validator definition must be multi list")

    multi_list = validator_definition["multi"]
    if not isinstance(multi_list, Mapping):
        raise ValueError("Multi list must be a mapping")

    if "0" not in multi_list:
        raise ValueError("Multi list must contain validators for block number 0")

    for multi_list_key, multi_list_entry in multi_list.items():
        if not multi_list_key.isdigit():
            raise ValueError("Multi list keys must be stringified ints")

        if not isinstance(multi_list_entry, Mapping):
            raise ValueError("Multi list entries must be a mapping")

        if not len(multi_list_entry.keys()) == 1:
            raise ValueError("Multi list entries must have exactly one key")

        for multi_list_entry_type, multi_list_entry_data in multi_list_entry.items():
            if multi_list_entry_type not in ["list", "safeContract", "contract"]:
                raise ValueError(
                    "Multi list entries must be one of list, safeContract or contract"
                )

            if multi_list_entry_type == "list":
                if not isinstance(multi_list_entry_data, list):
                    raise ValueError("Static validator list definition must be a list")

                if len(multi_list_entry_data) < 1:
                    raise ValueError("Static validator list must not be empty")

                if any(
                    not is_hex_address(address) for address in multi_list_entry_data
                ):
                    raise ValueError(
                        "Static validator list must only contain hex addresses"
                    )

            elif multi_list_entry_type in ["safeContract", "contract"]:
                if not is_hex_address(multi_list_entry_data):
                    raise ValueError(
                        "Validator contract address must be a single hex address"
                    )
            else:
                assert False, "Unreachable. Multi list entry type has already been validated."


# Added for compatibility with the upcoming pull request
class ValidatorDefinitionRange(NamedTuple):
    transition_to_height: int
    transition_from_height: int
    is_contract: bool
    contract_address: Optional[bytes] = None
    validators: Optional[List[bytes]] = None


def get_validator_definition_ranges(validator_definition):
    validate_validator_definition(validator_definition)

    sorted_definition = sorted(
        # Lambda tuple destructuring has been removed from Python 3 (https://www.python.org/dev/peps/pep-3113/) :-(
        validator_definition["multi"].items(), key=lambda item: int(item[0])

    )

    items, nexts = tee(sorted_definition, 2)
    nexts = chain(islice(nexts, 1, None), [[None, None]])

    result = []
    for (range_height, range_config), (next_range_height, _) in zip(items, nexts):
        [(config_type, config_data)] = range_config.items()

        validators = None
        contract_address = None
        if config_type == "list":
            is_contract = False
            validators = config_data
        elif config_type in ["contract", "safeContract"]:
            is_contract = True
            contract_address = config_data
        else:
            assert False, "Unreachable. Invalid config type."

        result.append(
            ValidatorDefinitionRange(
                transition_from_height=range_height,
                transition_to_height=next_range_height,
                is_contract=is_contract,
                validators=validators,
                contract_address=contract_address,
            )
        )

    return result


def make_primary_function(validator_definition):
    validate_validator_definition(validator_definition)

    multi_list = {}
    for start_block_number_str, multi_list_entry in validator_definition[
        "multi"
    ].items():
        start_block_number = int(start_block_number_str)
        addresses = [
            to_canonical_address(address) for address in multi_list_entry["list"]
        ]
        multi_list[start_block_number] = addresses

    descending_start_block_numbers = sorted(multi_list.keys(), reverse=True)

    def get_primary_for_step(step):
        start_block_number = next(
            start_block_number
            for start_block_number in descending_start_block_numbers
            if step >= start_block_number
        )
        current_validator_list = multi_list[start_block_number]
        return current_validator_list[step % len(current_validator_list)]

    return get_primary_for_step
