import pytest

from monitor.db import AlreadyExists
from monitor.blocks import get_proposer, get_canonicalized_block, get_step

from tests.data_generation import (
    random_address,
    random_private_key,
    random_step,
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


def test_retrieve_single_block_by_proposer_and_step(populated_db, inserted_blocks):
    for block in inserted_blocks:
        proposer = get_proposer(get_canonicalized_block(block))
        step = get_step(block)

        retrieved_blocks = populated_db.get_blocks_by_proposer_and_step(proposer, step)

        assert len(retrieved_blocks) == 1

        retrieved_block = retrieved_blocks[0]

        assert retrieved_block.hash == block.hash
        assert retrieved_block.step == step
        assert retrieved_block.proposer == proposer


def test_retrieve_no_blocks_by_proposer_and_step_for_non_existing_combinations(
    populated_db, inserted_blocks
):
    block = inserted_blocks[-1]

    proposer = get_proposer(get_canonicalized_block(block))
    proposer_without_block = (
        random_address()
    )  # Collision rate with an actual proposer is most like zero.

    step = get_step(block)
    step_without_block = random_step()

    assert not populated_db.get_blocks_by_proposer_and_step(
        proposer, step_without_block
    )
    assert not populated_db.get_blocks_by_proposer_and_step(
        proposer_without_block, step
    )


def test_retrieve_multiple_blocks_by_proposer_and_step(empty_db):
    proposer_privkey = random_private_key()
    proposer = proposer_privkey.public_key.to_canonical_address()
    step = random_step()

    block_one = make_block(proposer_privkey=proposer_privkey, step=step)
    empty_db.insert(block_one)

    block_two = make_block(proposer_privkey=proposer_privkey, step=step)
    empty_db.insert(block_two)

    retrieved_blocks = empty_db.get_blocks_by_proposer_and_step(proposer, step)

    assert len(retrieved_blocks) == 2

    retrieved_block_one, retrieved_block_two = retrieved_blocks

    assert retrieved_block_one.hash == block_one.hash
    assert retrieved_block_two.hash == block_two.hash

    assert retrieved_block_one.proposer == proposer
    assert retrieved_block_two.proposer == proposer

    assert retrieved_block_one.step == step
    assert retrieved_block_two.step == step


def test_empty_db_is_empty(empty_db):
    assert empty_db.is_empty()


def test_non_empty_db_is_not_empty(populated_db):
    assert not populated_db.is_empty()


def test_load_pickled_non_existing_key(empty_db):
    assert empty_db.load_pickled("foo") is None


def test_load_store_pickled(empty_db):
    empty_db.store_pickled("foo", dict(bar=1))
    assert empty_db.load_pickled("foo") == dict(bar=1)


def test_store_pickled_existing(empty_db):
    empty_db.store_pickled("foo", dict(bar=1))
    empty_db.store_pickled("foo", dict(bar=2))
    assert empty_db.load_pickled("foo") == dict(bar=2)


def test_persistent_session(empty_db):
    assert empty_db.current_session is None
    with empty_db.persistent_session() as session:
        assert empty_db.current_session is session
    assert empty_db.current_session is None


def test_session_handling_rollback(empty_db):
    branch = make_branch(10)

    with empty_db.persistent_session() as session:
        empty_db.insert_branch(branch)
        assert not empty_db.is_empty()
        session.rollback()

    assert empty_db.is_empty()


def test_session_handling_commit(empty_db):
    branch = make_branch(10)

    with empty_db.persistent_session() as session:
        empty_db.insert_branch(branch)
        assert not empty_db.is_empty()
        session.commit()

    assert not empty_db.is_empty()

    for block in branch:
        assert empty_db.contains(block.hash)
