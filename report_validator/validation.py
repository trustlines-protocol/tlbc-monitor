import click
from deploy_tools.files import validate_and_format_address, InvalidAddressException
from eth_utils import is_hex, is_0x_prefixed, decode_hex


def validate_address(ctx, param, value):
    try:
        return validate_and_format_address(value)
    except InvalidAddressException as e:
        raise click.BadParameter(
            f"A address parameter is not recognized to be an address: {value}"
        ) from e


def validate_signature(ctx, param, value):
    if is_hex(value) and is_0x_prefixed(value) and len(value) == 132:
        return decode_hex(value)
    else:
        raise click.BadParameter(
            f"A signature parameter seems to be not well structured: {value}"
        )


def validate_block_header(ctx, param, value):
    if is_hex(value) and is_0x_prefixed(value):
        return decode_hex(value)
    else:
        raise click.BadParameter(
            f"A block header parameter seems to be not well structured: {value}"
        )


def validate_equivocation_report_file(ctx, param, value):
    with open(value) as file:
        lines = file.read().splitlines()

    if not (
        lines[0].startswith("Proposer:")
        and lines[1].startswith("Block step:")
        and lines[2].startswith("Detection time:")
    ):
        raise click.BadParameter("Report file header does not fit!")

    if len(lines) < 21:
        raise click.BadParameter("Report file not long enough!")

    return {
        "unsigned_block_header_one": validate_block_header(None, None, lines[11]),
        "signature_one": validate_signature(None, None, lines[14]),
        "unsigned_block_header_two": validate_block_header(None, None, lines[17]),
        "signature_two": validate_signature(None, None, lines[20]),
    }
