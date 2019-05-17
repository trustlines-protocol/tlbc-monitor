import json
import random
from typing import List, Sequence, Tuple
import os

import pytest

from eth_tester import EthereumTester
from web3 import Web3
from web3.contract import Contract
from web3.providers.eth_tester import EthereumTesterProvider

from eth_utils.toolz import sliding_window

from monitor.validators import (
    ValidatorDefinitionRange,
    Epoch,
    ContractEpochFetcher,
    EpochFetcher,
    get_static_epochs,
)


@pytest.fixture(autouse=True)
def seed_rng():
    random.seed(0)


def get_random_address():
    return bytes(random.randint(0, 255) for _ in range(20))


@pytest.fixture
def tester():
    return EthereumTester()


@pytest.fixture
def w3(tester):
    provider = EthereumTesterProvider(tester)
    return Web3(provider)


@pytest.fixture
def contracts_json():
    dirname = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.join(dirname, "contracts.json")
    with open(filename) as f:
        return json.load(f)


@pytest.fixture
def validator_set_abi(contracts_json):
    return contracts_json["TestValidatorSet"]["abi"]


@pytest.fixture
def validator_set_bytecode(contracts_json):
    return contracts_json["TestValidatorSet"]["bytecode"]


@pytest.fixture
def validator_set_contract(w3, validator_set_bytecode, validator_set_abi):
    return w3.eth.contract(abi=validator_set_abi, bytecode=validator_set_bytecode)


def test_get_static_epochs():
    VALIDATOR1 = b"\x00" * 20
    VALIDATOR2 = b"\x01" * 20
    CONTRACT_ADDRESS = b"\xff" * 20

    ranges = [
        ValidatorDefinitionRange(
            enter_height=0,
            leave_height=5,
            is_contract=False,
            contract_address=None,
            validators=[VALIDATOR1],
        ),
        ValidatorDefinitionRange(
            enter_height=5,
            leave_height=10,
            is_contract=True,
            contract_address=CONTRACT_ADDRESS,
            validators=None,
        ),
        ValidatorDefinitionRange(
            enter_height=10,
            leave_height=None,
            is_contract=False,
            contract_address=None,
            validators=[VALIDATOR2],
        ),
    ]
    epochs = get_static_epochs(ranges)
    assert epochs == [Epoch(0, [VALIDATOR1], 0), Epoch(10, [VALIDATOR2], 2)]


def initialize_scenario(
    validator_set_contract: Contract, transition_heights: Sequence[int] = None
) -> Tuple[List[ValidatorDefinitionRange], List[Contract]]:
    transition_heights = transition_heights or []

    w3 = validator_set_contract.web3

    validator_definition_ranges = []
    contracts: List[Contract] = []
    for enter_height, leave_height in sliding_window(2, transition_heights + [None]):
        deployment_tx_hash = validator_set_contract.constructor().transact()
        deployment_receipt = w3.eth.waitForTransactionReceipt(deployment_tx_hash)
        contract = w3.eth.contract(
            address=deployment_receipt.contractAddress, abi=validator_set_contract.abi
        )
        contracts.append(contract)

        validator_definition_ranges.append(
            ValidatorDefinitionRange(
                enter_height=enter_height,
                leave_height=leave_height,
                is_contract=True,
                contract_address=contracts[-1].address,
                validators=None,
            )
        )

    return validator_definition_ranges, contracts


def initialize_validators(contract: Contract) -> List[bytes]:
    validators = [get_random_address() for _ in range(2)]
    tx_hashes = [
        contract.functions.init(validators).transact(),
        contract.functions.testFinalizeChange().transact(),
    ]
    for tx_hash in tx_hashes:
        contract.web3.eth.waitForTransactionReceipt(tx_hash)
    return validators


def mine_until(w3: Web3, tester: EthereumTester, height: int) -> None:
    if height < w3.eth.blockNumber:
        raise ValueError("Target block height is already past")
    tester.mine_blocks(height - w3.eth.blockNumber)


def change_validators(contract: Contract) -> Tuple[List[bytes], int]:
    validators = [get_random_address() for _ in range(2)]
    tx_hashes = [
        contract.functions.testChangeValiatorSet(validators).transact(),
        contract.functions.testFinalizeChange().transact(),
    ]
    receipts = [
        contract.web3.eth.waitForTransactionReceipt(tx_hash) for tx_hash in tx_hashes
    ]
    return validators, max(receipt.blockNumber for receipt in receipts)


def test_fetch_first_epoch(w3, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    validators = initialize_validators(contract)

    fetcher = ContractEpochFetcher(w3, val_def[0], 0)

    epochs = fetcher.fetch_new_epochs()
    assert epochs == [Epoch(100, validators, 0)]


def test_fetch_second_time(w3, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    initialize_validators(contract)

    fetcher = ContractEpochFetcher(w3, val_def[0], 0)
    fetcher.fetch_new_epochs()

    epochs = fetcher.fetch_new_epochs()
    assert epochs == []


def test_fetch_single_update(w3, tester, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    initialize_validators(contract)

    fetcher = ContractEpochFetcher(w3, val_def[0], 0)
    fetcher.fetch_new_epochs()

    mine_until(w3, tester, 105)
    validators, height = change_validators(contract)

    epochs = fetcher.fetch_new_epochs()
    assert epochs == [Epoch(height, validators, 0)]


def test_fetch_multiple_updates(w3, tester, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    initialize_validators(contract)

    fetcher = ContractEpochFetcher(w3, val_def[0], 0)
    fetcher.fetch_new_epochs()

    mine_until(w3, tester, 105)
    validators1, height1 = change_validators(contract)

    mine_until(w3, tester, height1 + 10)
    validators2, height2 = change_validators(contract)

    epochs = fetcher.fetch_new_epochs()
    assert epochs == [Epoch(height1, validators1, 0), Epoch(height2, validators2, 0)]


def test_contract_epoch_fetcher_initialization(w3, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    fetcher = ContractEpochFetcher(w3, val_def[0], 0)
    assert fetcher.earliest_fetched_epoch is None
    assert fetcher.latest_fetched_epoch is None
    assert fetcher.last_fetch_height is None


def test_contract_epoch_fetcher_udpates_last_fetch_height(
    w3, tester, validator_set_contract
):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    fetcher = ContractEpochFetcher(w3, val_def[0], 0)

    mine_until(w3, tester, 123)
    fetcher.fetch_new_epochs()
    assert fetcher.last_fetch_height == 123


def test_contract_epoch_fetcher_sets_earliest_epoch_once(
    w3, tester, validator_set_contract
):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    validators1 = initialize_validators(contract)

    fetcher = ContractEpochFetcher(w3, val_def[0], 0)

    fetcher.fetch_new_epochs()

    assert fetcher.earliest_fetched_epoch == Epoch(100, validators1, 0)

    mine_until(w3, tester, 105)
    validators2, height2 = change_validators(contract)

    fetcher.fetch_new_epochs()
    assert fetcher.earliest_fetched_epoch == Epoch(100, validators1, 0)


def test_contract_epoch_fetcher_sets_latest_epoch(w3, tester, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    validators1 = initialize_validators(contract)

    fetcher = ContractEpochFetcher(w3, val_def[0], 0)
    fetcher.fetch_new_epochs()

    assert fetcher.latest_fetched_epoch == Epoch(100, validators1, 0)

    mine_until(w3, tester, 105)
    validators2, height2 = change_validators(contract)

    fetcher.fetch_new_epochs()
    assert fetcher.latest_fetched_epoch == Epoch(height2, validators2, 0)


def test_epoch_fetcher_fetches_from_all_contracts(w3, tester, validator_set_contract):
    val_def, (contract1, contract2) = initialize_scenario(
        validator_set_contract, transition_heights=[100, 200]
    )
    fetcher = EpochFetcher(w3, val_def)

    validators1 = initialize_validators(contract1)
    validators2 = initialize_validators(contract2)

    epochs = fetcher.fetch_new_epochs()
    assert epochs == [Epoch(100, validators1, 0), Epoch(200, validators2, 1)]


def test_epoch_fetcher_ignores_stale_contracts(w3, tester, validator_set_contract):
    val_def, (contract1, contract2) = initialize_scenario(
        validator_set_contract, transition_heights=[100, 200]
    )
    fetcher = EpochFetcher(w3, val_def)

    initialize_validators(contract1)
    mine_until(w3, tester, 250)
    initialize_validators(contract2)
    fetcher.fetch_new_epochs()

    change_validators(contract1)
    epochs = fetcher.fetch_new_epochs()
    assert epochs == []


def test_epoch_fetcher_updates_last_fetch_height(w3, tester, validator_set_contract):
    val_def, (contract,) = initialize_scenario(
        validator_set_contract, transition_heights=[100]
    )
    initialize_validators(contract)

    fetcher = EpochFetcher(w3, val_def)
    assert fetcher.last_fetch_height == 0
    fetcher.fetch_new_epochs()
    assert fetcher.last_fetch_height == w3.eth.blockNumber

    mine_until(w3, tester, 50)
    fetcher.fetch_new_epochs()
    assert fetcher.last_fetch_height == 50
