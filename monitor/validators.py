from collections.abc import Mapping
import operator
from typing import NamedTuple, cast, List, Optional

from web3 import Web3

from eth_utils import is_hex_address


VALIDATOR_CONTRACT_ABI = None


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


class Epoch(NamedTuple):
    start_height: int
    validators: List[bytes]


class ValidatorDefinitionRange(NamedTuple):
    # first block height at which this definition is considered
    transition_to_height: int
    # first block height at which the following definition is considered, or None if it is the last
    # definition
    transition_from_height: Optional[int]
    is_contract: bool
    contract_address: Optional[bytes]
    validators: Optional[List[bytes]]


class PrimaryOracle:
    def __init__(self) -> None:
        self._epochs: List[Epoch] = []

    def get_primary(self, block_height: int, step: int):
        validators = self._get_validators(block_height)
        index = step % len(validators)
        return validators[index]

    def _get_validators(self, block_height: int) -> List[bytes]:
        if not self._epochs:
            raise ValueError("No epochs have been added yet")
        started_epochs = [
            epoch for epoch in self._epochs if epoch.start_height <= block_height
        ]
        if not started_epochs:
            raise ValueError(f"Block #{block_height} is earlier than the first epoch")
        return started_epochs[-1].validators

    def add_epoch(self, epoch: Epoch) -> None:
        if not epoch.validators:
            raise ValueError("Validators set of epoch is empty")
        unsorted_epochs = self._epochs + [epoch]
        sorted_epochs = sorted(unsorted_epochs, key=operator.attrgetter("start_height"))
        self._epochs = sorted_epochs


class EpochFetcher:
    def __init__(
        self, w3: Web3, validator_definition_ranges: List[ValidatorDefinitionRange]
    ) -> None:
        self._w3 = w3
        self._validator_definition_ranges = validator_definition_ranges
        self._latest_fetched_epoch_start_height = 0

    def fetch_new_epochs(self) -> List[Epoch]:
        contracts_to_check = [
            definition_range.contract_address
            for definition_range in self._validator_definition_ranges
            if (
                definition_range.is_contract
                and (
                    definition_range.transition_from_height is None
                    or definition_range.transition_from_height
                    > self._latest_fetched_epoch_start_height
                )
            )
        ]

        new_epochs: List[Epoch] = []
        for contract_address in contracts_to_check:
            new_epochs_in_contract = self._fetch_new_epochs_from_contract(
                cast(bytes, contract_address)
            )
            new_epochs += new_epochs_in_contract

        new_epoch_start_heights = [epoch.start_height for epoch in new_epochs]
        assert all(
            epoch_start_height > self._latest_fetched_epoch_start_height
            for epoch_start_height in new_epoch_start_heights
        )
        self._latest_fetched_epoch_start_height = max(
            new_epoch_start_heights, default=self._latest_fetched_epoch_start_height
        )

        return new_epochs

    def _fetch_new_epochs_from_contract(self, contract_address: bytes) -> List[Epoch]:
        contract = self._w3.eth.contract(
            address=contract_address, abi=VALIDATOR_CONTRACT_ABI
        )
        epoch_start_heights = contract.call().getEpochStartHeights()

        new_epoch_start_heights = [
            epoch_start_height
            for epoch_start_height in epoch_start_heights
            if epoch_start_height > self._latest_fetched_epoch_start_height
        ]

        new_epochs = []
        for epoch_start_height in new_epoch_start_heights:
            validators = contract.call().getValidators(epoch_start_height)
            epoch = Epoch(start_height=epoch_start_height, validators=validators)
            new_epochs.append(epoch)

        return new_epochs
