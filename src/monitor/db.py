from typing import Any
import pickle
import contextlib
from web3.datastructures import AttributeDict

from eth_utils.toolz import sliding_window

from sqlalchemy import Column, Integer, String, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists
from sqlalchemy.exc import IntegrityError, DatabaseError

from monitor.blocks import get_canonicalized_block, get_proposer, get_step

Base: Any = declarative_base()


class DBError(Exception):
    pass


class AlreadyExists(DBError):
    pass


class NotFound(DBError):
    pass


class InvalidDataError(DBError):
    """Raise to indicate that the db data is invalid"""

    pass


class Block(Base):
    __tablename__ = "blocks"

    hash = Column(String(length=32), primary_key=True)
    proposer = Column(String(length=20), index=True)
    step = Column(Integer, index=True)


class NamedBlob(Base):
    __tablename__ = "pickled"
    name = Column(String(length=20), primary_key=True)
    blob = Column(LargeBinary())


def blocks_from_block_dicts(block_dicts):
    return [
        Block(
            hash=block_dict.hash,
            proposer=get_proposer(get_canonicalized_block(block_dict)),
            step=get_step(block_dict),
        )
        for block_dict in block_dicts
    ]


def ensure_branch(block_dicts):
    """make sure we really have a branch, i.e. each block is the parent block
    of the following block

    raises ValueError if block_dicts is not a branch.
    """
    for parent, child in sliding_window(2, block_dicts):
        if child.parentHash != parent.hash:
            raise ValueError("Given branch is not connected")


def load_pickled(session, name):
    """load the pickled NamedBlob object with the given name"""
    named_blob = session.query(NamedBlob).get(name)
    if named_blob is None:
        return None
    else:
        return pickle.loads(named_blob.blob)


def store_pickled(session, name, obj):
    """store the given python obj as pickled NamedBlob object under the given name"""
    pickled_state = pickle.dumps(obj)
    named_blob = session.query(NamedBlob).get(name)
    if named_blob is None:
        named_blob = NamedBlob(name=name, blob=pickled_state)
    else:
        named_blob.blob = pickled_state
    session.add(named_blob)


class BlockDB:
    def __init__(self, engine):
        self.engine = engine

        self.session_class = sessionmaker(bind=self.engine)
        try:
            Base.metadata.create_all(self.engine)
        except DatabaseError as e:
            raise InvalidDataError(f"Corrupt db state: {e}") from e
        self.current_session = None

    def _get_session(self):
        return self.current_session or self.session_class()

    @contextlib.contextmanager
    def persistent_session(self):
        assert self.current_session is None
        self.current_session = self.session_class()
        yield self.current_session
        self.current_session = None

    def insert(self, block_dict: AttributeDict) -> None:
        self.insert_branch([block_dict])

    def insert_branch(self, block_dicts):
        ensure_branch(block_dicts)
        blocks = blocks_from_block_dicts(block_dicts)
        session = self._get_session()
        session.add_all(blocks)

        try:
            session.flush()
            if self.current_session is None:
                session.commit()
        except IntegrityError:
            raise AlreadyExists(
                "At least one block from the given branch already exists"
            )

    def is_empty(self):
        session = self._get_session()
        return not session.query(session.query(Block).exists()).scalar()

    def contains(self, block_hash: bytes) -> bool:
        session = self._get_session()
        return session.query(exists().where(Block.hash == block_hash)).scalar()

    def get_blocks_by_proposer_and_step(self, proposer: bytes, step: int):
        session = self._get_session()
        query = session.query(Block).filter(
            Block.proposer == proposer, Block.step == step
        )
        return query.all()

    def store_pickled(self, name, obj):
        session = self._get_session()
        store_pickled(session, name, obj)
        if self.current_session is None:
            session.commit()

    def load_pickled(self, name):
        session = self._get_session()
        try:
            return load_pickled(session, name)
        except Exception as e:
            raise InvalidDataError(f"Invalid {name}: {e}") from e
