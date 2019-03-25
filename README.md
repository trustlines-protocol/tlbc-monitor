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

In production, the monitor will usually run inside a Docker container and interact with another container housing a Parity client connected to the Trustlines blockchain. Here's a command typical for such a setting:

```
docker run -v </path/to/chain-spec.json>:/config/chain-spec.json -v </path/to/reports/dir>:/reports tlbc-monitor -c /config/chain-spec.json -u http://172.17.0.2:8545 -r /reports -o 0.5
```
