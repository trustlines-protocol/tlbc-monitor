import click

from deploy_tools.deploy import build_transaction_options
from deploy_tools.cli import (
    jsonrpc_option,
    keystore_option,
    gas_option,
    gas_price_option,
    nonce_option,
    auto_nonce_option,
    connect_to_json_rpc,
    retrieve_private_key,
    get_nonce,
)

from .core import report_malicious_validator
from .validation import (
    validate_address,
    validate_signature,
    validate_block_header,
    validate_equivocation_report_file,
)


reporting_contract_option = click.option(
    "--contract-address",
    help="The address of the reporting contract, can either be the ValidatorSet contract on the Trustlines chain "
    "for removing a validator or the ValidatorSlasher contract on the Ethereum main chain to slash a validator.",
    type=str,
    required=True,
    callback=validate_address,
)

unsigned_block_header_one_option = click.option(
    "--unsigned-block-header-one",
    help="Unsigned and RLP encoded block header one of the equivocation proof.",
    type=str,
    required=True,
    callback=validate_block_header,
)

signature_one_option = click.option(
    "--signature-one",
    help="Signature related to the block one of the equivocation proof.",
    type=str,
    required=True,
    callback=validate_signature,
)

unsigned_block_header_two_option = click.option(
    "--unsigned-block-header-two",
    help="Unsigned and RLP encoded block header two of the equivocation proof.",
    type=str,
    required=True,
    callback=validate_block_header,
)

signature_two_option = click.option(
    "--signature-two",
    help="Signature related to the block two of the equivocation proof.",
    type=str,
    required=True,
    callback=validate_signature,
)

equivocation_report_option = click.option(
    "--equivocation-report",
    help="Equivocation report file by the monitor tool.",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    callback=validate_equivocation_report_file,
)


@click.group()
def main():
    pass


@main.command(
    short_help=(
        "Report a validator who has equivocated on the Trustlines Chain."
        "Requires to provide all equivocation proof information manually as arguments."
        "The report can be sent to the ValidatorSet contract on the TL chain "
        "or to the ValidatorSlasher contract on the Ethereum main chain"
    )
)
@keystore_option
@gas_option
@gas_price_option
@nonce_option
@auto_nonce_option
@jsonrpc_option
@reporting_contract_option
@unsigned_block_header_one_option
@signature_one_option
@unsigned_block_header_two_option
@signature_two_option
def report_via_arguments(
    keystore: str,
    gas: int,
    gas_price: int,
    nonce: int,
    auto_nonce: bool,
    jsonrpc: str,
    contract_address,
    unsigned_block_header_one,
    signature_one,
    unsigned_block_header_two,
    signature_two,
) -> None:

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)

    nonce = get_nonce(
        web3=web3, nonce=nonce, auto_nonce=auto_nonce, private_key=private_key
    )

    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )

    tx_hash = report_malicious_validator(
        web3,
        transaction_options,
        private_key,
        contract_address,
        unsigned_block_header_one,
        signature_one,
        unsigned_block_header_two,
        signature_two,
    )

    click.echo(f"Transaction hash: {tx_hash}")


@main.command(
    short_help=(
        "Report a validator who has equivocated on the Trustlines chain."
        "Equivocation proof information are parsed from a report file."
        "The report can be sent to the ValidatorSet contract on the TL chain "
        "or to the ValidatorSlasher contract on the Ethereum main chain"
    )
)
@keystore_option
@gas_option
@gas_price_option
@nonce_option
@auto_nonce_option
@jsonrpc_option
@reporting_contract_option
@equivocation_report_option
def report_via_file(
    keystore: str,
    gas: int,
    gas_price: int,
    nonce: int,
    auto_nonce: bool,
    jsonrpc: str,
    contract_address,
    equivocation_report,
) -> None:

    web3 = connect_to_json_rpc(jsonrpc)
    private_key = retrieve_private_key(keystore)

    nonce = get_nonce(
        web3=web3, nonce=nonce, auto_nonce=auto_nonce, private_key=private_key
    )

    transaction_options = build_transaction_options(
        gas=gas, gas_price=gas_price, nonce=nonce
    )

    tx_hash = report_malicious_validator(
        web3,
        transaction_options,
        private_key,
        contract_address,
        equivocation_report["unsigned_block_header_one"],
        equivocation_report["signature_one"],
        equivocation_report["unsigned_block_header_two"],
        equivocation_report["signature_two"],
    )

    click.echo(f"Transaction hash: {tx_hash}")
