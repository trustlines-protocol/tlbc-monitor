import pytest

from monitor.db import AlreadyExists
from monitor.blocks import get_proposer, get_canonicalized_block

from tests.data_generation import (
    random_address,
    random_private_key,
    make_block,
    make_branch,
)


@pytest.fixture
def inserted_blocks():
    return [make_block() for _ in range(3)]


@pytest.fixture
def populated_db(empty_db, inserted_blocks):
    for block in inserted_blocks:
        empty_db.insert(block)
    return empty_db


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


def test_retrieve_single_block_by_proposer_and_height(populated_db, inserted_blocks):
    block = inserted_blocks[0]
    proposer = get_proposer(get_canonicalized_block(block))
    height = block.number

    retrieved_blocks = populated_db.get_blocks_by_proposer_and_height(proposer, height)

    assert len(retrieved_blocks) == 1

    retrieved_block = retrieved_blocks[0]

    assert retrieved_block.hash == block.hash
    assert retrieved_block.height == height
    assert retrieved_block.proposer == proposer


def test_retrieve_no_blocks_by_proposer_and_height_for_non_existing_combinations(populated_db, inserted_blocks):
    block = inserted_blocks[-1]

    proposer = get_proposer(get_canonicalized_block(block))
    proposer_without_block = random_address()  # Collision rate with an actual proposer is most like zero.

    height = block.number
    height_without_block = 123  # This number is related to the random_block_height generation function.

    assert not populated_db.get_blocks_by_proposer_and_height(proposer, height_without_block)
    assert not populated_db.get_blocks_by_proposer_and_height(proposer_without_block, height)


def test_retrieve_multiple_blocks_by_proposer_and_height(empty_db):
    proposer_privkey = random_private_key()
    proposer = proposer_privkey.public_key.to_canonical_address()
    height = 1

    block_one = make_block(proposer_privkey=proposer_privkey, height=height)
    empty_db.insert(block_one)

    block_two = make_block(proposer_privkey=proposer_privkey, height=height)
    empty_db.insert(block_two)

    retrieved_blocks = empty_db.get_blocks_by_proposer_and_height(proposer, height)

    assert len(retrieved_blocks) == 2

    retrieved_block_one, retrieved_block_two = retrieved_blocks

    assert retrieved_block_one.hash == block_one.hash
    assert retrieved_block_two.hash == block_two.hash

    assert retrieved_block_one.proposer == proposer
    assert retrieved_block_two.proposer == proposer

    assert retrieved_block_one.height == height
    assert retrieved_block_two.height == height


def test_empty_db_is_empty(empty_db):
    assert empty_db.is_empty()


def test_non_empty_db_is_not_empty(populated_db):
    assert not populated_db.is_empty()
