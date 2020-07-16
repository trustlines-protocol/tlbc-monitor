# TLBC Monitor

The TLBC Monitor is a program that monitors the Trustlines Blockchain and log
misbehaving or not well performing validators.

## Installation

The [quickstart
setup](https://github.com/trustlines-protocol/blockchain#setup-with-the-quickstart-script)
provides an easy way to run a Trustlines Blockchain node with monitor connected
to that. The following instructions describe a manual installation Clone the
repository, create a Python `virtualenv`, and execute the following commands:

```sh
pip install -c constraints.txt -r requirements.txt
pip install -c constraints.txt --editable .
```

## Building the Docker image

To build the Docker image, run the following command in the root directory of the repository:

```sh
docker build --tag tlbc-monitor .
```

## Usage

`tlbc-monitor` provides the following CLI interface:

```
Usage: tlbc-monitor [OPTIONS]

Options:
  -u, --rpc-uri TEXT              URI of the node's JSON RPC server  [default:
                                  http://localhost:8540]
  -c, --chain-spec-path FILE      path to the chain spec file of the
                                  Trustlines blockchain  [required]
  -m, --watch-chain-spec          Continuously watch for changes in the chain
                                  spec file and stop if there are any
  -r, --report-dir DIRECTORY      path to the directory in which misbehavior
                                  reports will be created  [default: ./reports]
  -d, --db-dir DIRECTORY          path to the directory in which the database
                                  and application state will be stored
                                  [default: ./state]
  -o, --skip-rate FLOAT           maximum rate of assigned steps a validator
                                  can skip without being reported as offline
                                  [default: 0.5]
  -w, --offline-window INTEGER RANGE
                                  size in seconds of the time window
                                  considered when determining if validators
                                  are offline or not  [default: 86400]
  --sync-from TEXT                starting block  [default: -1000]
  --upgrade-db                    Allow to upgrade the database
                                  (experimental). Some skips will be missed
                                  around the upgrade time
  --version                       Print tlbc-monitor version information
  --help                          Show this message and exit.
```

The `--sync-from` argument is used to select a starting block, where the
synchronization starts. It can be given in multiple ways:

- a non-negative integer specifies a blocknumber
- a negative integer N selects the block -N blocks before the latest block
- a date in the format 'YYYY-MM-DD' selects the first block validated after that date.
- `genesis` selects the block with number 0
- `latest` selects the latest block

Please note that the actual block being used will differ, if the selected block
is less than 1000 blocks away from the latest block.

## Report Malicious Validators

When the monitor reports an equivocation by a malicious validator, it is
possible to remove that validator from the validator set and slash their deposit on the Ethereum main chain.
The information required to prove the equivocation can be found in the created report file
located at the directory defined with `--report-dir` (default `./reports`). The file is named
`equivocation_reports_for_proposer_0x...` followed by the address of the
malicious validator. There is one such file per validator who has equivocated.
Multiple violations by the same address will be attached to the end of the first
report in the same file. It does not matter which proof is chosen to slash / remove a validator.

To remove a validator from the validator set on the Trustlines chain, one needs
to send the proof to the `reportMaliciousValidator` function of the `ValidatorSet`
contract on the Trustlines chain. The currently active contract can be extracted
from the [chain specification
file](https://github.com/trustlines-protocol/blockchain/blob/master/chain/tlbc/tlbc-spec.json)

To slash the deposit of the validator on the main chain, one needs to send the proof to the
`reportMaliciousValidator` function of the `ValidatorSlasher` contract on the
Ethereum main chain. Please visit the [foundation
website](https://trustlines.foundation/auction.html) to checkout the current
auction contract and find the linked slashing address.

The `report-validator` tool can be used to simplify the report process. An
example call would look like this:

```sh
docker --rm --net="host" \
  --volume $(pwd)/reports:/reports \
  trustlines/report-validator:release \
  report-via-file \
  --contract-address 0x9Cc30A6088DB80F8a3B2b4d2f491AbC98559C59c \
  --equivocation-report /reports/equivocation_reports_for_proposer_0x505ab22ef8f3ae874dec92e60665ca490fb68192
```

In the above example, `./reports` is the directory containing the reports of
equivocating validators, including one for address
`0x505ab22ef8f3ae874dec92e60665ca490fb68192`. The exemplary contract where to report is
deployed at address `0x9Cc30A6088DB80F8a3B2b4d2f491AbC98559C59c`. The example
assumes a running _Parity_ node syncing the desired chain: Ethereum main chain
for slashing or Trustlines chain for removing a validator. The _Parity_ node is
expected to have an unlocked account to sign the transaction. Alternatively
the option `--keystore` can be specified to sign the transaction with a local
key. The URL of the node can be specified with the `--jsonrpc` option. Per
default it assumes that the JSON RPC endpoint is available on your local
machine at `http://127.0.0.1:8545`. Therefore, the above example is bound to
`--net="host"`. In case of a setup with the [quickstart
script](https://github.com/trustlines-protocol/blockchain#setup-with-the-quickstart-script),
the endpoint is not available to `localhost` for security reasons. Rather you
need to directly address the container. This can be done by connecting the
`report-validator` tool to the same network and use the name of the _Parity_
container. E.g., for slashing, this would require to set
`--net="tlbc_foreign-net"` for the _Docker_ container and point the tool to
`--jsonrpc http://tlbc_foreign-node_1:8545`. Run the following command to get
the exact values for your setup `docker ps --format "{{.Names}} {{.Networks}}"`.

Furthermore there are is the possibility to adjust the default transaction
options by using `--gas`, `--gas-price`, `--nounce` and `--auto-nounce`.
Checkout the `--help` for further information.

It is also possible to enter the equivocation proof information manually in case
no report file is available. It only differs in the way of providing these
information. All other options remain the same as described before.

```sh
docker --rm --net="host" \
  trustlines/report-validator:release \
  report-via-arguments \
  --contract-address 0x9Cc30A6088DB80F8a3B2b4d2f491AbC98559C59c \
  --unsigned-block-header-one 0xf901f9a08b0b6994dedb8765f7b39f95ec70a4e027812224b811cb7c95373998f3db5677a01dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d4934794505ab22ef8f3ae874dec92e60665ca490fb68192a02ab8e45aa54b0c26532eebe73d73b890887a047108dc9a5ce99f6cad89175b9ba056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421a056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421b901000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000090ffffffffffffffffffffffffed71d01501837a120080845cc6ef929fde8302010b8f5061726974792d457468657265756d86312e33342e30826c69 \
  --signature-one 0x6f34ee0b150bfba5fc88bf9e2731318dd35776606c91cff14bf2fd2ca4a10b726d96623efdf609c11311bb852b213b233298ea3e3cce5c5c96db627bbc2ddf2900 \
  --unsigned-block-header-two 0xf901f9a0e05e23fb6a3bec793185af81000e0f723fa14205d7ac262b7b8520ed8316cbe5a01dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d4934794505ab22ef8f3ae874dec92e60665ca490fb68192a0c7b66672d9f26caec060c8d91b9088344eb1210efc494b2593dbdc31481ab454a056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421a056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421b901000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000090fffffffffffffffffffffffffffffffe05837a120080845cc6ef929fde8302010b8f5061726974792d457468657265756d86312e33342e30826c69 \
  --signature-two 0x1671ba6903ce67cca8723b40f1759afa3945bdb66e5f0b6d62bed5bfda315c4a3a68a208deea14aedbe69848d6d1448764a2db82c35d097377d3f08f93c36b7701
```
