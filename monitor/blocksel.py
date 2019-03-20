"""allow selection of an initial block"""
import abc
import datetime


class ResolveBlock(metaclass=abc.ABCMeta):
    @classmethod
    @abc.abstractmethod
    def from_blockselector(cls, blocksel):
        pass

    @abc.abstractmethod
    def resolve_block(self, w3):
        pass


class ResolveBlockByNumber(ResolveBlock):
    """resolve a block by number"""

    @classmethod
    def from_blockselector(cls, blocksel):
        return cls(int(blocksel))

    def __init__(self, blocksel):
        self.blocknr = blocksel

    def resolve_block(self, w3):
        if self.blocknr < 0:
            blocknr = max(0, w3.eth.blockNumber + self.blocknr)
        else:
            blocknr = self.blocknr

        return w3.eth.getBlock(blocknr)


class ResolveGenesisBlock(ResolveBlock):
    @classmethod
    def from_blockselector(cls, blocksel):
        if blocksel not in ("genesis", "0"):
            raise ValueError()
        return cls()

    def resolve_block(self, w3):
        return w3.eth.getBlock(0)


class ResolveLatestBlock(ResolveBlock):
    """resolves to the latest block"""

    @classmethod
    def from_blockselector(cls, blocksel):
        if blocksel not in ("latest", "-0"):
            raise ValueError()
        return cls()

    def resolve_block(self, w3):
        return w3.eth.getBlock("latest")


def parse_date(s):
    """parse date from given string in format YYYY-MM-DD returns an aware UTC
    datetime object for the start of that day"""
    return datetime.datetime.strptime(s, "%Y-%m-%d").replace(
        tzinfo=datetime.timezone.utc
    )


class ResolveBlockByDate(ResolveBlock):
    """resolves to the first block after a given date

    This does a binary search to find that block
    """

    @classmethod
    def from_blockselector(cls, blocksel):
        return cls(parse_date(blocksel).timestamp())

    def __init__(self, timestamp):
        self.timestamp = timestamp

    def resolve_block(self, w3):
        lower_block = w3.eth.getBlock(0)
        upper_block = w3.eth.getBlock("latest")
        while upper_block.number - lower_block.number > 1:
            middle = w3.eth.getBlock((lower_block.number + upper_block.number) // 2)
            if self.timestamp >= middle.timestamp:
                lower_block = middle
            else:
                upper_block = middle
        return lower_block


def make_blockresolver(blockselector):
    """given a blockselector string, try to return a blockresolver"""
    for cls in [
        ResolveLatestBlock,
        ResolveGenesisBlock,
        ResolveBlockByNumber,
        ResolveBlockByDate,
    ]:
        try:
            return cls.from_blockselector(blockselector)
        except ValueError:
            pass
    raise ValueError("Could not parse blockselector")
