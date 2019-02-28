import structlog
from eth_utils import encode_hex

from monitor.blocks import get_proposer, get_canonicalized_block


class EquivocationReporter:
    """Reporter that will report equivocations on detection.

    The user of this reporter has to make sure to write the
    block into the database before calling the reporter with this block.
    """

    logger = structlog.get_logger("monitor.equivocation_reporter")

    def __init__(self, db):
        self.db = db
        self.report_callbacks = []

    def register_report_callback(self, callback):
        """
        The callback functions are called with a single parameter which is a list
        of block hashes (list[bytes]) which are equivocated.
        """
        self.report_callbacks.append(callback)

    def __call__(self, block):
        proposer = get_proposer(get_canonicalized_block(block))
        height = block.number
        blocks_by_same_proposer_on_same_height = self.db.get_blocks_by_proposer_and_height(
            proposer, height
        )
        block_hashes_by_same_proposer_on_same_height = [
            block.hash for block in blocks_by_same_proposer_on_same_height
        ]

        # Ensures that the block has been added to the database, otherwise the following logic will not work.
        assert block.hash in block_hashes_by_same_proposer_on_same_height

        if len(block_hashes_by_same_proposer_on_same_height) >= 2:
            self.logger.info(
                "detected equivocation", proposer=encode_hex(proposer), height=height
            )

            for callback in self.report_callbacks:
                callback(block_hashes_by_same_proposer_on_same_height)
