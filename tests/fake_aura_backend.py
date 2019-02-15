from eth_tester import PyEVMBackend
from eth_tester.exceptions import ValidationError
from eth_tester.normalization import DefaultNormalizer
from eth_tester.normalization.common import (
    normalize_dict,
)
from eth_tester.normalization.outbound import (
    BLOCK_NORMALIZERS,
)
from eth_tester.validation import DefaultValidator
from eth_tester.validation.common import (
    validate_bytes,
    validate_dict,
)
from eth_tester.validation.outbound import (
    BLOCK_VALIDATORS,
    validate_canonical_address,
)

from eth_utils import (
    encode_hex,
    is_dict,
)

from hexbytes import HexBytes
from eth_utils.toolz import (
    identity,
)

from web3.datastructures import AttributeDict
from web3.middleware import (
    construct_formatting_middleware,
)
from web3.providers.eth_tester.middleware import (
    block_key_remapper,
)
from web3.utils.formatters import (
    apply_formatter_if,
)

from watchdog.blocks import calculate_block_signature


class FakeAuraBackend(PyEVMBackend):

    def __init__(self, genesis_parameters=None, genesis_state=None, private_keys=None):
        super().__init__(genesis_parameters, genesis_state)

    def mine_blocks(self, num_blocks=1, coinbase=None):
        accounts = self.get_accounts()

        if len(accounts) == 0:
            raise ValueError("Cannot mine block as no accounts have been added")
        if coinbase is None:
            coinbase = accounts[0]

        if coinbase not in accounts:
            raise ValueError("Cannot mine block using foreign account")

        return super().mine_blocks(num_blocks, coinbase)

    def get_block_with_aura_fields(self, block):
        parity_fields = {
            "author": block["miner"],
            "sealFields": [b"", b""],
        }
        block_with_parity_fields = AttributeDict({**block, **parity_fields})
        signature = self._get_signature_for_block(block_with_parity_fields)
        return {
            **block,
            **parity_fields,
            "signature": signature,
        }

    def _get_signature_for_block(self, block):
        if block["number"] == 0:
            return b"\x00" * 65
        else:
            signer = block["author"]
            try:
                private_key = self._key_lookup[signer]
            except KeyError:
                raise ValueError(
                    f"Cannot sign block as private key for coinbase address "
                    f"{encode_hex(block['miner'])} is unknown"
                )
            else:
                block_with_web3_keys = fix_web3_keys(block_key_remapper(block))
                return calculate_block_signature(block_with_web3_keys, private_key).to_bytes()

    def get_block_by_hash(self, block_hash, full_transaction=True):
        block = super().get_block_by_hash(block_hash, full_transaction)
        return self.get_block_with_aura_fields(block)

    def get_block_by_number(self, block_number, full_transaction=True):
        block = super().get_block_by_number(block_number, full_transaction)
        return self.get_block_with_aura_fields(block)


def validate_seal_fields(seal_fields):
    if len(seal_fields) != 2:
        raise ValidationError("There must be two seal fields")

    for seal_field in seal_fields:
        validate_bytes(seal_field)


def validate_signature(signature):
    validate_bytes(signature)

    if len(signature) != 65:
        raise ValidationError("Signatures must have a length of 65 bytes")


class FakeAuraValidator(DefaultValidator):

    block_validators = {
        **BLOCK_VALIDATORS,
        **{
            "sealFields": validate_seal_fields,
            "author": validate_canonical_address,
            "signature": validate_signature,
        },
    }

    @classmethod
    def validate_outbound_block(cls, block):
        return validate_dict(block, cls.block_validators)


class FakeAuraNormalizer(DefaultNormalizer):

    block_normalizers = {
        **BLOCK_NORMALIZERS,
        **{
            "sealFields": identity,
            "author": encode_hex,
            "signature": encode_hex,
        },
    }

    @classmethod
    def normalize_outbound_block(cls, block):
        return normalize_dict(block, cls.block_normalizers)


def fix_web3_keys(block):
    return AttributeDict({
        **block,
        "receiptsRoot": HexBytes(block["receipts_root"]),
        "logsBloom": block["logs_bloom"],
    })


key_renaming_middleware = construct_formatting_middleware(
    result_formatters={
        "eth_getBlockByHash": apply_formatter_if(
            is_dict,
            fix_web3_keys,
        ),
        "eth_getBlockByNumber": apply_formatter_if(
            is_dict,
            fix_web3_keys,
        ),
    }
)
