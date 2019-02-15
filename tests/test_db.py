import random

import pytest

from web3.datastructures import (
    MutableAttributeDict,
)

from hexbytes import HexBytes
from eth_utils.toolz import (
    sliding_window,
)

from eth_keys import keys

from watchdog.db import (
    AlreadyExists,
    NotFound,
)
from watchdog.blocks import (
    get_canonicalized_block,
    calculate_block_signature,
)


random.seed(0)


@pytest.fixture
def inserted_blocks():
    return [make_block() for _ in range(3)]


@pytest.fixture
def populated_db(empty_db, inserted_blocks):
    for block in inserted_blocks:
        empty_db.insert(block)
    return empty_db


def random_hash():
    return bytes(random.randint(0, 255) for _ in range(32))


def random_address():
    return bytes(random.randint(0, 255) for _ in range(20))


def random_height():
    return random.randint(0, 100)


def random_privkey():
    return keys.PrivateKey(random_hash())


def make_block(block_hash=None, parent_hash=None, proposer_privkey=None, height=None):
    if proposer_privkey is None:
        proposer_privkey = random_privkey()

    block = MutableAttributeDict({
        "hash": HexBytes(block_hash or random_hash()),
        "sealFields": [HexBytes(b""), HexBytes(b"")],

        "parentHash": HexBytes(parent_hash or random_hash()),
        "sha3Uncles": HexBytes(random_hash()),
        "author": proposer_privkey.public_key.to_address(),
        "stateRoot": HexBytes(random_hash()),
        "transactionsRoot": HexBytes(random_hash()),
        "receiptsRoot": HexBytes(random_hash()),
        "logsBloom": HexBytes(b"\x00" * 256),
        "difficulty": 0,
        "number": height if height is not None else random_height(),
        "gasLimit": 0,
        "gasUsed": 0,
        "timestamp": 0,
        "extraData": HexBytes(random_hash()),

        # add proposer private key to simplify testing
        "privkey": proposer_privkey,

        "signature": "",
    })
    block["signature"] = calculate_block_signature(get_canonicalized_block(block), proposer_privkey).to_hex()
    return block


def make_branch(length):
    hashes = [random_hash() for _ in range(length)]
    return [
        make_block(block_hash=child_hash, parent_hash=parent_hash, height=height)
        for height, (parent_hash, child_hash) in enumerate(sliding_window(2, hashes))
    ]


def test_insert_block(populated_db):
    block = make_block()
    populated_db.insert(block)
    assert populated_db.contains(block.hash)


def test_insert_hash_twice(populated_db, inserted_blocks):
    for block in inserted_blocks:
        with pytest.raises(AlreadyExists):
            populated_db.insert(block)


def test_insert_branch(populated_db):
    branch = make_branch(10)
    populated_db.insert_branch(branch)
    for block in branch:
        assert populated_db.contains(block.hash)


def test_insert_broken_branch(populated_db):
    branch = make_branch(5) + make_branch(5)
    with pytest.raises(ValueError):
        populated_db.insert_branch(branch)


def test_insert_branch_with_existing_block(populated_db):
    branch = make_branch(10)
    block = branch[5]
    populated_db.insert(block)
    with pytest.raises(AlreadyExists):
        populated_db.insert_branch(branch)


def test_contains_inserted_block(populated_db, inserted_blocks):
    for block in inserted_blocks:
        assert populated_db.contains(block.hash)


def test_does_not_contain_not_inserted_block(populated_db):
    for block in [make_block() for _ in range(3)]:
        assert not populated_db.contains(block.hash)


def test_retrieve_proposer_by_hash(populated_db, inserted_blocks):
    for block in inserted_blocks:
        retrieved_proposer = populated_db.get_proposer_by_hash(block.hash)
        assert retrieved_proposer == block.privkey.public_key.to_canonical_address()


def test_retrieve_proposer_of_nonexistant_block(populated_db):
    with pytest.raises(NotFound):
        populated_db.get_proposer_by_hash(random_address())


def test_retrieve_hashes_by_height(empty_db):
    random_blocks = [make_block(height=height) for height in [10, 20, 30]]
    blocks_at_15 = [make_block(height=15) for _ in range(5)]

    for block in random_blocks + blocks_at_15:
        empty_db.insert(block)

    assert set(empty_db.get_hashes_by_height(15)) == set(block.hash for block in blocks_at_15)


def test_retrieve_missing_hashes_by_height(empty_db):
    random_blocks = [make_block(height=height) for height in [10, 20, 30]]

    for block in random_blocks:
        empty_db.insert(block)

    assert empty_db.get_hashes_by_height(15) == []


def test_empty_db_is_empty(empty_db):
    assert empty_db.is_empty()


def test_non_empty_db_is_not_empty(populated_db):
    assert not populated_db.is_empty()
