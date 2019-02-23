from collections.abc import Mapping

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

        if not isinstance(multi_list_entry, Mapping) or not list(
            multi_list_entry.keys()
        ) == ["list"]:
            raise ValueError("Multi list entries must be lists")

        if len(multi_list_entry["list"]) == 0:
            raise ValueError("Validator lists must not be empty")

        if any(not is_hex_address(address) for address in multi_list_entry["list"]):
            raise ValueError("Multi list entries must only contain hex addresses")


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
