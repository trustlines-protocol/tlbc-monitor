import random
from eth_keys import keys
from hexbytes import HexBytes
from web3.datastructures import MutableAttributeDict
from monitor.blocks import get_canonicalized_block, calculate_block_signature
from eth_utils.toolz import sliding_window


random_generator = random.Random(0)


def random_hash():
    return bytes(random_generator.randint(0, 255) for _ in range(32))


def random_address():
    return bytes(random_generator.randint(0, 255) for _ in range(20))


def random_private_key():
    return keys.PrivateKey(random_hash())


def random_block_height():
    return random_generator.randint(0, 100)


def make_block(
    *,
    block_hash=None,
    parent_hash=None,
    proposer_privkey=None,
    height=None,
    timestamp=0
):
    if proposer_privkey is None:
        proposer_privkey = random_private_key()

    block = MutableAttributeDict(
        {
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
            "number": height if height is not None else random_block_height(),
            "gasLimit": 0,
            "gasUsed": 0,
            "timestamp": timestamp,
            "extraData": HexBytes(random_hash()),
            "privkey": proposer_privkey,  # add proposer private key to simplify testing.
            "signature": "",
        }
    )

    block["signature"] = calculate_block_signature(
        get_canonicalized_block(block), proposer_privkey
    ).to_hex()
    return block


def make_branch(length):
    hashes = [random_hash() for _ in range(length)]
    return [
        make_block(block_hash=child_hash, parent_hash=parent_hash, height=height)
        for height, (parent_hash, child_hash) in enumerate(sliding_window(2, hashes))
    ]
