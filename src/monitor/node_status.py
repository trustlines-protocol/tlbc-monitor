import logging
import time
from typing import Dict, List, Optional

import attr

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True)
class NodeStatus:
    is_syncing: bool
    block_number: int
    latest_synced_block: int
    syncing_map: Dict
    client_version: str
    is_light_node: Optional[bool]
    block_gap: List[int]


def get_node_status_parity(w3):
    client_version = w3.clientVersion
    block_number = w3.eth.blockNumber

    syncing_map = w3.eth.syncing or None

    chain_status = w3.manager.request_blocking("parity_chainStatus", [])
    node_kind = w3.manager.request_blocking("parity_nodeKind", [])

    if chain_status.blockGap is not None:
        block_gap = [int(x, 16) for x in chain_status.blockGap]
    else:
        block_gap = None

    is_light_node = node_kind.capability == "light"

    if block_gap and not is_light_node:  # warp mode syncing
        is_syncing = True
        latest_synced_block = block_gap[0] - 1
    elif syncing_map:
        is_syncing = True
        latest_synced_block = syncing_map.currentBlock
    else:
        is_syncing = False
        latest_synced_block = block_number

    return NodeStatus(
        is_syncing=is_syncing,
        block_number=block_number,
        latest_synced_block=latest_synced_block,
        syncing_map=syncing_map,
        client_version=client_version,
        is_light_node=is_light_node,
        block_gap=block_gap,
    )


def get_node_status_geth(w3):
    client_version = w3.clientVersion
    block_number = w3.eth.blockNumber
    syncing_map = w3.eth.syncing or None
    is_syncing = bool(syncing_map)
    return NodeStatus(
        is_syncing=is_syncing,
        block_number=block_number,
        latest_synced_block=block_number,
        syncing_map=syncing_map,
        client_version=client_version,
        is_light_node=None,
        block_gap=None,
    )


def get_node_status(w3):
    if w3.clientVersion.startswith("Parity") or w3.clientVersion.startswith(
        "OpenEthereum"
    ):
        return get_node_status_parity(w3)
    else:
        return get_node_status_geth(w3)


def wait_for_node_status(w3, predicate, sleep_time=30.0):
    while True:
        node_status = get_node_status(w3)
        if predicate(node_status):
            return node_status
        time.sleep(sleep_time)
