import pytest

from web3.datastructures import AttributeDict

from monitor.blocks import (
    get_canonicalized_block,
    get_proposer,
    calculate_block_signature,
)

from eth_utils.toolz import merge

from eth_keys import keys

from .kovan_test_data import KOVAN_GENESIS_BLOCK, KOVAN_BLOCKS


@pytest.mark.parametrize("block", KOVAN_BLOCKS)
def test_get_proposer(block):
    canonicalized_block = get_canonicalized_block(block)
    # check the signer against the author field, which is the same address for the test data
    assert get_proposer(canonicalized_block) == canonicalized_block.author


@pytest.mark.parametrize("block", KOVAN_BLOCKS)
@pytest.mark.parametrize(
    "private_key",
    [
        keys.PrivateKey(b"\x11" * 32),
        keys.PrivateKey(b"\x22" * 32),
        keys.PrivateKey(b"\x33" * 32),
    ],
)
def test_signing(block, private_key):
    canonicalized_block = get_canonicalized_block(block)
    signature = calculate_block_signature(canonicalized_block, private_key)
    resigned_block = AttributeDict(
        merge(canonicalized_block, {"signature": signature.to_bytes()})
    )
    assert get_proposer(resigned_block) == private_key.public_key.to_canonical_address()


def test_get_proposer_of_genesis_block():
    canonicalized_genesis_block = get_canonicalized_block(KOVAN_GENESIS_BLOCK)
    assert get_proposer(canonicalized_genesis_block) == b"\x00" * 20
