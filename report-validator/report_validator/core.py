import json
import pkg_resources

from deploy_tools.deploy import send_function_call_transaction
from eth_utils import encode_hex


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
        abi=get_contract_abi("ValidatorSet"), address=validator_set_contract_address
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

    print(f"Transaction hash: {encode_hex(transaction_receipt.transactionHash)}")


def get_contract_abi(contract_name: str):
    resource_package = __name__
    json_string = pkg_resources.resource_string(resource_package, "contracts.json")
    json_dict = json.loads(json_string)
    return json_dict[contract_name]["abi"]
