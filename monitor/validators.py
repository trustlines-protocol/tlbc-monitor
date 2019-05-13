import bisect
from collections.abc import Mapping
from copy import copy
from itertools import chain, takewhile, dropwhile
import operator
from typing import NamedTuple, cast, List, Optional, Sequence

from eth_utils import is_hex_address, to_canonical_address, decode_hex
from eth_utils.toolz import sliding_window, last

from web3 import Web3


VALIDATOR_CONTRACT_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "", "type": "uint256"}],
        "name": "pendingValidators",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_epochStart", "type": "uint256"}],
        "name": "getValidators",
        "outputs": [{"name": "", "type": "address[]"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getEpochStartHeights",
        "outputs": [{"name": "", "type": "uint256[]"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [],
        "name": "finalizeChange",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_rlpUnsignedHeaderOne", "type": "bytes"},
            {"name": "_signatureOne", "type": "bytes"},
            {"name": "_rlpUnsignedHeaderTwo", "type": "bytes"},
            {"name": "_signatureTwo", "type": "bytes"},
        ],
        "name": "reportMaliciousValidator",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "finalized",
        "outputs": [{"name": "", "type": "bool"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "getValidators",
        "outputs": [{"name": "_validators", "type": "address[]"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "_validators", "type": "address[]"}],
        "name": "init",
        "outputs": [{"name": "_success", "type": "bool"}],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "systemAddress",
        "outputs": [{"name": "", "type": "address"}],
        "payable": False,
        "stateMutability": "view",
        "type": "function",
    },
    {"payable": False, "stateMutability": "nonpayable", "type": "fallback"},
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "_parentHash", "type": "bytes32"},
            {"indexed": False, "name": "_newSet", "type": "address[]"},
        ],
        "name": "InitiateChange",
        "type": "event",
    },
]


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
                assert (
                    False
                ), "Unreachable. Multi list entry type has already been validated."


# Added for compatibility with the upcoming pull request
class ValidatorDefinitionRange(NamedTuple):
    enter_height: int
    leave_height: int
    is_contract: bool
    contract_address: Optional[bytes] = None
    validators: Optional[List[bytes]] = None


def get_validator_definition_ranges(validator_definition):
    validate_validator_definition(validator_definition)

    sorted_definition = sorted(
        # Lambda tuple destructuring has been removed from Python 3 (https://www.python.org/dev/peps/pep-3113/) :-(
        validator_definition["multi"].items(),
        key=lambda item: int(item[0]),
    )

    result = []

    # Iterate over all configurations. Add an extra empty item for the sliding window to slide to the very end.
    # Alternatively we'd have to do some additional processing which would further complicate the code
    for (range_height, range_config), (next_range_height, _) in sliding_window(
        2, chain(sorted_definition, [[None, None]])
    ):
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
                enter_height=range_height,
                leave_height=next_range_height,
                is_contract=is_contract,
                validators=validators,
                contract_address=contract_address,
            )
        )

    return result


class Epoch(NamedTuple):
    start_height: int
    validators: List[bytes]
    validator_definition_index: int


class ValidatorDefinitionRange(NamedTuple):
    # first block height at which this definition is considered
    transition_to_height: int
    # first block height at which the following definition is considered, or None if it is the last
    # definition
    transition_from_height: Optional[int]
    is_contract: bool
    contract_address: Optional[bytes]
    validators: Optional[List[bytes]]


def get_static_epochs(
    validator_definition_ranges: List[ValidatorDefinitionRange]
) -> List[Epoch]:
    epochs = []

    for index, validator_definition_range in enumerate(validator_definition_ranges):
        if not validator_definition_range.is_contract:
            assert validator_definition_range.validators is not None

            epoch = Epoch(
                start_height=validator_definition_range.transition_to_height,
                validators=validator_definition_range.validators,
                validator_definition_index=index,
            )
            epochs.append(epoch)

    return epochs


class PrimaryOracle:
    def __init__(self, static_epochs: Sequence[Epoch] = None) -> None:
        self._epochs = {epoch.start_height: epoch for epoch in static_epochs or []}
        self._ordered_start_heights = sorted(
            epoch.start_height for epoch in self._epochs.values()
        )

    def get_primary(self, *, height: int, step: int):
        validators = self._get_validators(height)
        index = step % len(validators)
        return validators[index]

    def _get_validators(self, block_height: int) -> List[bytes]:
        if not self._epochs:
            raise ValueError("No epochs have been added yet")

        try:
            epoch_start_height = last(
                takewhile(
                    lambda start_height: start_height <= block_height,
                    self._ordered_start_heights,
                )
            )
        except IndexError:
            raise ValueError(f"Block #{block_height} is earlier than the first epoch")
        else:
            epoch = self._epochs[epoch_start_height]
            return epoch.validators

    def add_epoch(self, epoch: Epoch) -> None:
        if not epoch.validators:
            raise ValueError("Validator set of epoch is empty")

        if self._is_relevant(epoch):
            if epoch.start_height not in self._epochs:
                bisect.insort(self._ordered_start_heights, epoch.start_height)
            self._epochs[epoch.start_height] = epoch

            self._remove_epochs_rendered_obsolete(epoch)

    def _is_relevant(self, epoch: Epoch) -> bool:
        earlier_epoch_start_heights = takewhile(
            lambda start_height: start_height <= epoch.start_height,
            self._ordered_start_heights,
        )
        try:
            previous_epoch_start_height = last(earlier_epoch_start_heights)
        except IndexError:
            return True
        else:
            previous_epoch = self._epochs[previous_epoch_start_height]
            return (
                previous_epoch.validator_definition_index
                <= epoch.validator_definition_index
            )

    def _remove_epochs_rendered_obsolete(self, inserted_epoch: Epoch) -> None:
        later_epoch_indices_and_start_heights = dropwhile(
            lambda index_and_height: index_and_height[1] <= inserted_epoch.start_height,
            enumerate(self._ordered_start_heights),
        )

        indices_to_remove = []
        for index, start_height in later_epoch_indices_and_start_heights:
            epoch = self._epochs[start_height]
            if (
                epoch.validator_definition_index
                < inserted_epoch.validator_definition_index
            ):
                indices_to_remove.append(index)
            else:
                break

        for index in reversed(indices_to_remove):
            removed_start_height = self._ordered_start_heights.pop(index)
            self._epochs.pop(removed_start_height)


class ContractEpochFetcher:
    def __init__(
        self,
        w3: Web3,
        validator_definition_range: ValidatorDefinitionRange,
        validator_definition_index: int,
    ) -> None:
        if not validator_definition_range.is_contract:
            raise ValueError(
                "Given validator definition range doesn't specify a contract"
            )

        self._w3 = w3
        self._contract = w3.eth.contract(
            address=validator_definition_range.contract_address,
            abi=VALIDATOR_CONTRACT_ABI,
        )

        self._transition_to_height = validator_definition_range.transition_to_height
        self._validator_definition_index = validator_definition_index

        self._last_fetch_height: Optional[int] = None
        self._earliest_fetched_epoch: Optional[Epoch] = None
        self._latest_fetched_epoch: Optional[Epoch] = None

    @property
    def earliest_fetched_epoch(self) -> Optional[Epoch]:
        return self._earliest_fetched_epoch

    @property
    def latest_fetched_epoch(self) -> Optional[Epoch]:
        return self._latest_fetched_epoch

    @property
    def last_fetch_height(self) -> Optional[int]:
        return self._last_fetch_height

    def fetch_new_epochs(self) -> List[Epoch]:
        self._last_fetch_height = self._w3.eth.blockNumber
        epoch_start_heights = self._contract.call().getEpochStartHeights()

        # epoch start heights will only be updated in finalizeChange which is called at most once
        # per block
        assert len(set(epoch_start_heights)) == len(epoch_start_heights)
        assert sorted(epoch_start_heights) == epoch_start_heights

        new_epoch_start_heights = [
            epoch_start_height
            for epoch_start_height in epoch_start_heights
            if (
                self.latest_fetched_epoch is None
                or epoch_start_height > self.latest_fetched_epoch.start_height
            )
        ]

        new_epochs = []
        for epoch_start_height in new_epoch_start_heights:
            validators = [
                decode_hex(validator)
                for validator in self._contract.call().getValidators(epoch_start_height)
            ]
            epoch = Epoch(
                start_height=max(epoch_start_height, self._transition_to_height),
                validators=validators,
                validator_definition_index=self._validator_definition_index,
            )
            new_epochs.append(epoch)

        if new_epochs:
            if self.earliest_fetched_epoch is None:
                self._earliest_fetched_epoch = new_epochs[0]
            self._latest_fetched_epoch = new_epochs[-1]

        return new_epochs


class EpochFetcher:
    def __init__(
        self, w3: Web3, validator_definition_ranges: List[ValidatorDefinitionRange]
    ) -> None:
        self._w3 = w3
        self._validator_definition_ranges = validator_definition_ranges
        self._contract_epoch_fetchers = [
            ContractEpochFetcher(self._w3, validator_definition_range, index)
            for index, validator_definition_range in enumerate(
                self._validator_definition_ranges
            )
            if validator_definition_range.is_contract
        ]

    def fetch_new_epochs(self) -> List[Epoch]:
        new_epochs: List[Epoch] = []
        for fetcher in self._contract_epoch_fetchers:
            epochs = fetcher.fetch_new_epochs()
            new_epochs += epochs

        self._remove_stale_fetchers()

        return new_epochs

    def _remove_stale_fetchers(self) -> None:
        while self._pop_first_fetcher_if_stale():
            continue

    def _pop_first_fetcher_if_stale(self) -> Optional[ContractEpochFetcher]:
        if len(self._contract_epoch_fetchers) == 0:
            return None

        first_fetcher = self._contract_epoch_fetchers[0]
        if first_fetcher.last_fetch_height is None:
            return None

        try:
            next_fetched_epoch = next(
                fetcher.earliest_fetched_epoch
                for fetcher in self._contract_epoch_fetchers[1:]
                if fetcher.earliest_fetched_epoch is not None
            )
        except StopIteration:
            return None
        else:
            if first_fetcher.last_fetch_height >= next_fetched_epoch.start_height:
                return self._contract_epoch_fetchers.pop(0)
            else:
                return None
