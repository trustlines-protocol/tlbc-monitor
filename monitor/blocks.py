import rlp

from web3.datastructures import AttributeDict

from eth_utils import decode_hex, keccak

from eth_keys import keys


EMPTY_SIGNATURE = b"\x00" * 65
EMPTY_ADDRESS = b"\x00" * 20


def get_canonicalized_block(block_dict):
    return AttributeDict(
        {
            "parentHash": bytes(block_dict.parentHash),
            "sha3Uncles": bytes(block_dict.sha3Uncles),
            "author": decode_hex(block_dict.author),
            "stateRoot": bytes(block_dict.stateRoot),
            "transactionsRoot": bytes(block_dict.transactionsRoot),
            "receiptsRoot": bytes(block_dict.receiptsRoot),
            "logsBloom": bytes(block_dict.logsBloom),
            "difficulty": block_dict.difficulty,
            "number": block_dict.number,
            "gasLimit": block_dict.gasLimit,
            "gasUsed": block_dict.gasUsed,
            "timestamp": block_dict.timestamp,
            "extraData": bytes(block_dict.extraData),
            "sealFields": block_dict.sealFields,
            "signature": decode_hex(block_dict.signature),
        }
    )


def get_proposer(canonicalized_block):
    """Extract the signer from a block as retrieved from Parity via its JSON RPC interface."""
    if canonicalized_block.signature == EMPTY_SIGNATURE:
        return EMPTY_ADDRESS

    message = bare_hash(canonicalized_block)
    signature = keys.Signature(canonicalized_block.signature)
    recovered_public_key = keys.ecdsa_recover(message, signature)
    return recovered_public_key.to_canonical_address()


def bare_hash(canonicalized_block):
    """Return the hash of a block excluding its seal fields."""
    assert len(canonicalized_block.sealFields) >= 2
    if len(canonicalized_block.sealFields) > 2:
        raise ValueError(
            "Bare hash for blocks with empty step transitions is not supported"
        )

    serialized = [
        canonicalized_block.parentHash,
        canonicalized_block.sha3Uncles,
        canonicalized_block.author,
        canonicalized_block.stateRoot,
        canonicalized_block.transactionsRoot,
        canonicalized_block.receiptsRoot,
        canonicalized_block.logsBloom,
        canonicalized_block.difficulty,
        canonicalized_block.number,
        canonicalized_block.gasLimit,
        canonicalized_block.gasUsed,
        canonicalized_block.timestamp,
        canonicalized_block.extraData,
    ]
    return keccak(rlp.encode(serialized))


def calculate_block_signature(canonicalized_block, private_key):
    message = bare_hash(canonicalized_block)
    signature = private_key.sign_msg_hash(message)
    return signature
