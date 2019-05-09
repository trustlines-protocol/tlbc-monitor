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

        if not isinstance(multi_list_entry, Mapping):
            raise ValueError("Multi list entries must be a mapping")

        if not len(multi_list_entry.keys()) == 1:
            raise ValueError("Multi list entries must have exactly one key")

        for multi_list_entry_type, multi_list_entry_data in multi_list_entry.items():
            if multi_list_entry_type not in ["list", "safeContract", "contract"]:
                raise ValueError("Multi list entries must be one of list, safeContract or contract")

            if multi_list_entry_type == "list":
                if not isinstance(multi_list_entry_data, list):
                    raise ValueError("Static validator list definition must be a list")

                if len(multi_list_entry_data) < 1:
                    raise ValueError("Static validator list must not be empty")

                if any(not is_hex_address(address) for address in multi_list_entry_data):
                    raise ValueError("Static validator list must only contain hex addresses")

            elif multi_list_entry_type in ["safeContract", "contract"]:
                if not is_hex_address(multi_list_entry_data):
                    raise ValueError("Dynamic validator list must be a single hex address")


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
