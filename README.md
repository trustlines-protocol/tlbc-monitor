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

```
Usage: tlbc-monitor [OPTIONS]

Options:
  -u, --rpc-uri TEXT              URI of the node's JSON RPC server  [default:
                                  http://localhost:8540]
  -c, --chain-spec-path FILE      path to the chain spec file of the
                                  Trustlines blockchain  [required]
  -r, --report-dir DIRECTORY      path to the directory in which misbehavior
                                  reports will be created  [default:
                                  <...>/tlbc-monitor/reports]
  -d, --db-dir DIRECTORY          path to the directory in which the database
                                  and application state will be stored
                                  [default: <...>/tlbc- monitor/state]
  -o, --skip-rate FLOAT           maximum rate of assigned steps a validator
                                  can skip without being reported as offline
                                  [default: 0.5]
  -w, --offline-window INTEGER RANGE
                                  size in seconds of the time window
                                  considered when determining if validators
                                  are offline or not  [default: 86400]
  --help                          Show this message and exit
```

In production, the monitor will usually run inside a Docker container and interact with another container housing a Parity client connected to the Trustlines blockchain. Here's a command typical for such a setting:

```
docker run -v </path/to/chain-spec.json>:/config/chain-spec.json -v </path/to/reports/dir>:/reports tlbc-monitor -c /config/chain-spec.json -u http://172.17.0.2:8545 -r /reports -o 0.5
```
