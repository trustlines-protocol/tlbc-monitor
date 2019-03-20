import random
from eth_keys import keys
from hexbytes import HexBytes
from web3.datastructures import MutableAttributeDict
from monitor.blocks import get_canonicalized_block, calculate_block_signature


random_generator = random.Random(0)


def random_hash():
    return bytes(random_generator.randint(0, 255) for _ in range(32))


def random_address():
    return bytes(random_generator.randint(0, 255) for _ in range(20))


def random_private_key():
    return keys.PrivateKey(random_hash())


def random_step():
    return random_generator.randint(0, 2**32)


def make_block(
    *,
    block_hash=None,
    parent_hash=None,
    proposer_privkey=None,
    step=None,
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
            "number": 0,
            "gasLimit": 0,
            "gasUsed": 0,
            "timestamp": 0,  # only needed to compute hash, not step
            "step": str(step if step is not None else random_step()),
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
    steps = range(length)

    hashes = [random_hash() for _ in range(length)]
    parent_hashes = [random_hash()] + hashes[:-1]

    return [
        make_block(
            block_hash=child_hash,
            parent_hash=parent_hash,
            step=step,
        )
        for child_hash, parent_hash, step
        in zip(hashes, parent_hashes, steps)
    ]
