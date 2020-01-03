from deploy_tools.deploy import send_function_call_transaction
from eth_utils import encode_hex


SIMPLE_REPORT_MALICIOUS_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_rlpUnsignedHeaderOne", "type": "bytes"},
            {"name": "_signatureOne", "type": "bytes"},
            {"name": "_rlpUnsignedHeaderTwo", "type": "bytes"},
            {"name": "_signatureTwo", "type": "bytes"},
        ],
        "name": "reportMaliciousValidator",
        "outputs": [],
        "payable": False,
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def report_malicious_validator(
    web3,
    transaction_options,
    private_key,
    validator_set_contract_address,
    unsigned_block_header_one,
    signature_one,
    unsigned_block_header_two,
    signature_two,
):
    validator_set_contract = web3.eth.contract(
        abi=SIMPLE_REPORT_MALICIOUS_ABI, address=validator_set_contract_address
    )

    report_validator_call = validator_set_contract.functions.reportMaliciousValidator(
        unsigned_block_header_one,
        signature_one,
        unsigned_block_header_two,
        signature_two,
    )

    transaction_receipt = send_function_call_transaction(
        report_validator_call,
        web3=web3,
        transaction_options=transaction_options,
        private_key=private_key,
    )

    return encode_hex(transaction_receipt.transactionHash)
