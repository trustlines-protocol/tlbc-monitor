from web3.datastructures import (
    AttributeDict,
)

from eth_utils.toolz import (
    sliding_window,
)

from sqlalchemy import (
    Column,
    Integer,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists
from sqlalchemy.exc import IntegrityError

from watchdog.blocks import (
    get_canonicalized_block,
    get_proposer,
)


Base = declarative_base()


class DBError(Exception):
    pass


class AlreadyExists(DBError):
    pass


class NotFound(DBError):
    pass


class Block(Base):
    __tablename__ = "blocks"

    hash = Column(String(length=32), primary_key=True)
    proposer = Column(String(length=20), index=True)
    height = Column(Integer, index=True)


class BlockDB:

    def __init__(self, engine):
        self.engine = engine

        self.session_class = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)

    def insert(self, block_dict: AttributeDict) -> None:
        self.insert_branch([block_dict])

    def insert_branch(self, block_dicts):
        for parent, child in sliding_window(2, block_dicts):
            if child.parentHash != parent.hash:
                raise ValueError("Given branch is not connected")

        session = self.session_class()
        blocks = [
            Block(
                hash=block_dict.hash,
                proposer=get_proposer(get_canonicalized_block(block_dict)),
                height=block_dict.number,
            )
            for block_dict in block_dicts
        ]
        session.add_all(blocks)

        try:
            session.commit()
        except IntegrityError:
            raise AlreadyExists(f"At least one block from the given branch already exists")

    def is_empty(self):
        session = self.session_class()
        return not session.query(session.query(Block).exists()).scalar()

    def contains(self, block_hash: bytes) -> bool:
        session = self.session_class()
        return session.query(exists().where(Block.hash == block_hash)).scalar()

    def get_blocks_by_proposer_and_height(self, proposer: bytes, height: int):
        session = self.session_class()
        query = session.query(Block).filter(Block.proposer == proposer, Block.height == height)
        return query.all()
