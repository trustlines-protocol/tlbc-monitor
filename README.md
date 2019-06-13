# TLBC Monitor

The TLBC Monitor is a program that monitors the Trustlines blockchain and notifies the user about misbehaving or underperforming validators.

## Installation

Clone the repository, create a virtualenv, and execute the following commands:

```
pip install -c constraints.txt -r requirements.txt
pip install -c constraints.txt --editable .
```

## Building the Docker image

To build the Docker image, run the following command in the root directory of the repository:

```
docker build -t tlbc-monitor .
```

## Usage

`tlbc-monitor` provides the following CLI interface:

```Usage: tlbc-monitor [OPTIONS]
Options:
  -u, --rpc-uri TEXT              URI of the node's JSON RPC server  [default:
                                  http://localhost:8540]
  -c, --chain-spec-path FILE      path to the chain spec file of the
                                  Trustlines blockchain  [required]
  -r, --report-dir DIRECTORY      path to the directory in which misbehavior
                                  reports will be created  [default: reports]
  -d, --db-dir DIRECTORY          path to the directory in which the database
                                  and application state will be stored
                                  [default: state]
  -o, --skip-rate FLOAT           maximum rate of assigned steps a validator
                                  can skip without being reported as offline
                                  [default: 0.5]
  -w, --offline-window INTEGER RANGE
                                  size in seconds of the time window
                                  considered when determining if validators
                                  are offline or not  [default: 86400]
  --sync-from TEXT                starting block  [default: -35000]
  --help                          Show this message and exit.
```

The --sync-from argument is used to select a starting block, where the
synchronization starts. It can be given in multiple ways:

- a non-negative integer specifies a blocknumber
- a negative integer N selects the block -N blocks before the latest block
- a date in the format 'YYYY-MM-DD' selects the first block validated after that date.
- `genesis` selects the block with number 0
- `latest` selects the latest block`

Please note that the actual block being used will differ, if the selected block
is less than 1000 blocks away from the latest block.

In production, the monitor will usually run inside a Docker container and
interact with another container housing a Parity client connected to the
Trustlines blockchain.

Here's a list of commands that will start the tlbc-monitoring service in case
you're running our recommended validator setup:

```
docker cp trustlines-testnet:/config/trustlines-spec.json .
mkdir reports state
docker run --name monitor -d --restart=always --link trustlines-testnet:parity -v $(pwd)/trustlines-spec.json:/config/trustlines-spec.json -v$(pwd)/reports:/reports -v$(pwd)/state:/state trustlines/tlbc-monitor -c /config/trustlines-spec.json -r /reports -d /state -u http://parity:8545 -o 0.5
```

## Report Malicious Validators

When the monitor reported an equivocation by a malicious validator, it is
possible to remove that validator from the validator set. The information to proof the
equivocation must be provided via the `reportMaliciousValidator` function to the
validator set contract. This information can be found at the created report
file, located at the directory defined with `--report-dir`. The file is named
like `equivocation_reports_for_proposer_0x...` followed by the address of the
malicious validator. There is one such file per validator who has equivocated.
Multiple violations by the same address will be attached to the end of the first
report. To remove a validator it does not matter which equivocation event is
choosen.

The `report-validator` tool can be used to simplify the report process. An
example call would look like this:

```sh
docker --rm --net="host" --volume $(pwd)/reports:/reports trustlines/report-validator report-via-file \
  --validator-set-contract-address 0x9Cc30A6088DB80F8a3B2b4d2f491AbC98559C59c \
  --equivocation-report /reports/equivocation_reports_for_proposer_0x505ab22ef8f3ae874dec92e60665ca490fb68192
```

Please make sure to use the currently active validator set contract address,
which can be found within the [chain
specification](https://github.com/trustlines-protocol/blockchain/blob/836e456d5ed8bcb576986e1c4cfe60603d14dcd0/config/trustlines-spec.json#L7).

The former example assumes a running _Parity_ node on `http://localhost:8545`
with an account unlocked to sign the transaction. The URL of the parity node can
be specified with the `--jsonrpc` option. `--keystore` can be specified to sign
the transaction with a local key instead of relying on an unlocked account.

Furthermore there are is the possibility to adjust the default transaction
options by using `--gas`, `--gas-price`, `--nounce` and `--auto-nounce`.
Checkout the `--help` for further information.

It is also possible to enter the equivocation proof information manually in case
no report file is available. It does only differ in the way of providing these
information. All other options remain the same as described before.

```sh
docker --rm --net="host" trustlines/report-validator report-via-arguments \
  --validator-set-contract-address 0x9Cc30A6088DB80F8a3B2b4d2f491AbC98559C59c \
  --unsigned-block-header-one 0xf901f9a08b0b6994dedb8765f7b39f95ec70a4e027812224b811cb7c95373998f3db5677a01dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d4934794505ab22ef8f3ae874dec92e60665ca490fb68192a02ab8e45aa54b0c26532eebe73d73b890887a047108dc9a5ce99f6cad89175b9ba056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421a056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421b901000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000090ffffffffffffffffffffffffed71d01501837a120080845cc6ef929fde8302010b8f5061726974792d457468657265756d86312e33342e30826c69 \
  --signature-one 0x6f34ee0b150bfba5fc88bf9e2731318dd35776606c91cff14bf2fd2ca4a10b726d96623efdf609c11311bb852b213b233298ea3e3cce5c5c96db627bbc2ddf2900 \
  --unsigned-block-header-two 0xf901f9a0e05e23fb6a3bec793185af81000e0f723fa14205d7ac262b7b8520ed8316cbe5a01dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d4934794505ab22ef8f3ae874dec92e60665ca490fb68192a0c7b66672d9f26caec060c8d91b9088344eb1210efc494b2593dbdc31481ab454a056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421a056e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421b901000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000090fffffffffffffffffffffffffffffffe05837a120080845cc6ef929fde8302010b8f5061726974792d457468657265756d86312e33342e30826c69 \
  --signature-two 0x1671ba6903ce67cca8723b40f1759afa3945bdb66e5f0b6d62bed5bfda315c4a3a68a208deea14aedbe69848d6d1448764a2db82c35d097377d3f08f93c36b7701
```
