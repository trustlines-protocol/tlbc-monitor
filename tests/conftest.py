import math

import pytest

from eth_tester import EthereumTester

from eth_keys import keys

from web3 import EthereumTesterProvider, Web3

from eth_utils import int_to_big_endian, to_checksum_address

from sqlalchemy import create_engine

from monitor.db import BlockDB
from monitor.validators import PrimaryOracle, Epoch


from tests.fake_aura_backend import (
    FakeAuraBackend,
    FakeAuraValidator,
    FakeAuraNormalizer,
    key_renaming_middleware,
)


@pytest.fixture
def eth_tester(address_to_private_key):
    eth_tester = EthereumTester(
        backend=FakeAuraBackend(),
        validator=FakeAuraValidator(),
        normalizer=FakeAuraNormalizer(),
    )

    existing_accounts = eth_tester.get_accounts()
    for address, private_key in address_to_private_key.items():
        if to_checksum_address(address) not in existing_accounts:
            eth_tester.add_account(private_key.to_hex())

    return eth_tester


@pytest.fixture
def address_to_private_key():
    private_keys = [
        keys.PrivateKey(int_to_big_endian(i).rjust(32, b"\x00")) for i in range(1, 10)
    ]
    return {
        private_key.public_key.to_canonical_address(): private_key
        for private_key in private_keys
    }


@pytest.fixture
def w3(eth_tester):
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    w3.middleware_stack.add(key_renaming_middleware)
    return w3


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def empty_db(engine):
    return BlockDB(engine)


@pytest.fixture
def validators():
    return [b"\x00" * 20, b"\x11" * 20, b"\x22" * 20]


@pytest.fixture
def primary_oracle(validators):
    primary_oracle = PrimaryOracle()
    primary_oracle.add_epoch(
        Epoch(start_height=0, validators=validators, validator_definition_index=0)
    )
    primary_oracle.max_height = math.inf
    return primary_oracle
