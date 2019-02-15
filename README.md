# TLBC Watchdog

The watchdog is a program that monitors the Trustlines blockchain and notifies the user about underperforming validators.

## Installation

Clone the repository, create a virtualenv, and execute the following commands:

```
pip install -c constraints.txt -r requirements.txt
pip install -c constraints.txt --editable .
```

## Building the Docker image

To build the Docker image, run the following command in the root directory of the repository:

```
docker build -t tlbc-watchdog .
```

## Usage

`tlbc-watchdog` provides the following CLI interface:

```
Usage: tlbc-watchdog [OPTIONS]

Options:
  -u, --rpc-uri TEXT          URI of the node's JSON RPC server  [default:
                              http://localhost:8540]
  -c, --chain-spec-path FILE  path to the chain spec file of the Trustlines
                              blockchain  [required]
  -r, --report-dir DIRECTORY  path to the directory in which misbehavior
                              reports will be created  [default:
                              /home/jannik/Repos/watchdog/reports]
  -s, --state-path FILE       path to the file in which the application
                              state will be stored to enable restarts
                              [default: /home/jannik/Repos/watchdog/state]
  -o, --skip-rate FLOAT       maximum rate of assigned steps a validator
                              can skip without being reported as offline
                              [default: 0.5]
  --help                      Show this message and exit.
```

In production, the watchdog will usually run inside a Docker container and interact with another container housing a Parity client connected to the Trustlines blockchain. Here's a command typical for such a setting:

```
docker run -v </path/to/chain-spec.json>:/config/chain-spec.json -v </path/to/reports/dir>:/reports tlbc-watchdog -c /config/chain-spec.json -u http://172.17.0.2:8545 -r /reports -o 0.5
```
