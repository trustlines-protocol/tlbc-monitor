import asyncio
import datetime
import json
from pathlib import Path
import pickle
import signal

from typing import Any, NamedTuple

import structlog

from sqlalchemy import create_engine

from web3 import Web3, HTTPProvider
from eth_utils import encode_hex
from eth_keys import keys

from monitor.db import BlockDB
from monitor.block_fetcher import BlockFetcher
from monitor.offline_reporter import OfflineReporter
from monitor.skip_reporter import SkipReporter
from monitor.equivocation_reporter import EquivocationReporter
from monitor.blocks import get_canonicalized_block, get_proposer, rlp_encoded_block
from monitor.validators import make_primary_function

import click


DEFAULT_RPC_URI = "http://localhost:8540"
default_report_dir = str(Path.cwd() / "reports")
default_db_dir = str(Path.cwd() / "state")
SKIP_FILE_NAME = "skips"
STATE_FILE_NAME = "state"
DB_FILE_NAME = "db"
SQLITE_URL_FORMAT = "sqlite:////{path}"


STEP_DURATION = 5
BLOCK_FETCH_INTERVAL = STEP_DURATION / 2
GRACE_PERIOD = 10  # number of blocks that have to pass before a missed block is counted
DEFAULT_OFFLINE_WINDOW_SIZE_IN_SECONDS = 24 * 60 * 60
DEFAULT_ALLOWED_SKIP_RATE = 0.5
MAX_REORG_DEPTH = (
    1000
)  # blocks at this depth in the chain are assumed to not be replaced

EQUIVOCATION_REPORT_TEMPLATE = """\
Proposer: {proposer_address}
Block height: {block_height}
Detection time: {detection_time}

Equivocated blocks:
{block_hash_timestamp_list}

Data for an equivocation proof by the first two equivocated blocks:

RLP encoded block header one:
{rlp_encoded_block_header_one}

Signature of block header one:
{signature_block_header_one}

RLP encoded block header two:
{rlp_encoded_block_header_two}

Signature of block header two:
{signature_block_header_two}

------------------------------

"""


def step_number_to_timestamp(step):
    return step * STEP_DURATION


class AppStateV1(NamedTuple):
    block_fetcher_state: Any
    skip_reporter_state: Any
    offline_reporter_state: Any


class App:

    logger = structlog.get_logger("monitor.main")

    def __init__(
        self,
        rpc_uri,
        chain_spec_path,
        report_dir,
        db_dir,
        skip_rate,
        offline_window_size,
    ):
        self.report_dir = report_dir
        self.db_dir = db_dir

        self.state_path = self.db_dir / STATE_FILE_NAME
        self.skip_file = open(report_dir / SKIP_FILE_NAME, "a")

        self.w3 = None
        self.get_primary_for_step = None

        self.db = None
        self.block_fetcher = None
        self.skip_reporter = None
        self.offline_reporter = None
        self.equivocation_reporter = None

        self._initialize_db(self.db_dir / DB_FILE_NAME)
        self._initialize_w3(rpc_uri)
        self._load_primary_function(chain_spec_path)
        self._initialize_reporters(self.state_path, skip_rate, offline_window_size)
        self._register_reporter_callbacks()
        self._running = False

    async def run(self):
        self._running = True
        try:
            self.logger.info("starting sync")
            while self._running:
                number_of_new_blocks = self.block_fetcher.fetch_and_insert_new_blocks()

                self.logger.info(
                    f"Syncing ({(int(self.block_fetcher.get_sync_status_percentage()))}%)",
                    head_hash=self.block_fetcher.head.hash,
                    head_number=self.block_fetcher.head.number,
                )

                if number_of_new_blocks == 0:
                    await asyncio.sleep(BLOCK_FETCH_INTERVAL)
                else:
                    await asyncio.sleep(0.01)
        finally:
            self.skip_file.close()
            self.dump_app_state()

    def stop(self):
        self.logger.info("Stopping... ")
        self._running = False

    def dump_app_state(self):
        with self.state_path.open("wb") as f:
            pickle.dump(self.app_state, f)

    @property
    def app_state(self):
        return AppStateV1(
            block_fetcher_state=self.block_fetcher.state,
            skip_reporter_state=self.skip_reporter.state,
            offline_reporter_state=self.offline_reporter.state,
        )

    #
    # Initialization
    #
    def _initialize_db(self, db_path):
        db_url = SQLITE_URL_FORMAT.format(path=db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(db_url)
        self.db = BlockDB(engine)

    def _initialize_w3(self, rpc_uri):
        self.w3 = Web3(HTTPProvider(rpc_uri))

    def _load_primary_function(self, chain_spec_path):
        with chain_spec_path.open("r") as f:
            chain_spec = json.load(f)
            validator_definition = chain_spec["engine"]["authorityRound"]["params"][
                "validators"
            ]
            self.get_primary_for_step = make_primary_function(validator_definition)

    def _initialize_reporters(self, state_path, skip_rate, offline_window_size):
        try:
            app_state = self._load_app_state(state_path)
        except FileNotFoundError:
            app_state = self._initialize_app_state()

        self.block_fetcher = BlockFetcher(
            state=app_state.block_fetcher_state,
            w3=self.w3,
            db=self.db,
            max_reorg_depth=MAX_REORG_DEPTH,
        )
        self.skip_reporter = SkipReporter(
            state=app_state.skip_reporter_state,
            get_primary_for_step=self.get_primary_for_step,
            grace_period=GRACE_PERIOD,
        )
        self.offline_reporter = OfflineReporter(
            state=app_state.offline_reporter_state,
            get_primary_for_step=self.get_primary_for_step,
            offline_window_size=offline_window_size,
            allowed_skip_rate=skip_rate,
        )
        self.equivocation_reporter = EquivocationReporter(db=self.db)

    def _load_app_state(self, state_path):
        with state_path.open("rb") as state_file:
            try:
                self.logger.info("loading state", path=state_path)
                app_state = pickle.load(state_file)
            except Exception:
                self.logger.critical("error loading state file")
                raise

        if not isinstance(app_state, AppStateV1):
            raise RuntimeError("state file has unexpected format")

        return app_state

    def _initialize_app_state(self):
        self.logger.info("no state file found, starting from genesis")
        return AppStateV1(
            block_fetcher_state=BlockFetcher.get_fresh_state(),
            skip_reporter_state=SkipReporter.get_fresh_state(),
            offline_reporter_state=OfflineReporter.get_fresh_state(),
        )

    def _register_reporter_callbacks(self):
        self.block_fetcher.register_report_callback(self.skip_reporter)
        self.block_fetcher.register_report_callback(self.equivocation_reporter)
        self.skip_reporter.register_report_callback(self.skip_logger)
        self.skip_reporter.register_report_callback(self.offline_reporter)
        self.offline_reporter.register_report_callback(self.offline_logger)
        self.equivocation_reporter.register_report_callback(self.equivocation_logger)

    #
    # Reporters
    #
    def skip_logger(self, validator, step):
        skip_timestamp = step_number_to_timestamp(step)
        self.skip_file.write(
            "{},{},{}\n".format(
                step,
                encode_hex(validator),
                datetime.datetime.utcfromtimestamp(skip_timestamp),
            )
        )

    def offline_logger(self, validator, steps):
        filename = (
            f"offline_report_{encode_hex(validator)}_steps_{min(steps)}_to_{max(steps)}"
        )
        with open(self.report_dir / filename, "w") as f:
            json.dump({"validator": encode_hex(validator), "missed_steps": steps}, f)

    def equivocation_logger(self, equivocated_block_hashes):
        """Log a reported equivocation event.

        Each new equivocation report is logged into a new file, using a counter
        as unique identifier.
        Logged information are the proposer of the blocks, the height at which
        all blocks have been equivocated and a list of all block hashes with
        their timestamp.
        Additionally two representing blocks are logged with their RLP encoded
        header and related signature, which can be used for an equivocation
        proof on reporting a validator.
        """

        # Use the first two blocks as representational data for the equivocation proof.
        block_hash_one = equivocated_block_hashes[0]
        block_hash_two = equivocated_block_hashes[1]

        block_one = get_canonicalized_block(self.w3.eth.getBlock(block_hash_one))
        block_two = get_canonicalized_block(self.w3.eth.getBlock(block_hash_two))

        block_hash_timestamp_list = ""

        for block_hash in equivocated_block_hashes:
            block = self.w3.eth.getBlock(block_hash)
            block_hash_timestamp_list += "{} ({})\n".format(
                encode_hex(block_hash),
                datetime.datetime.utcfromtimestamp(block.timestamp),
            )

        proposer_address = encode_hex(get_proposer(block_one))

        equivocation_report_template_variables = {
            "proposer_address": proposer_address,
            "block_height": block_one.number,
            "detection_time": datetime.datetime.utcnow(),
            "block_hash_timestamp_list": block_hash_timestamp_list,
            "rlp_encoded_block_header_one": rlp_encoded_block(block_one),
            "signature_block_header_one": keys.Signature(block_one.signature),
            "rlp_encoded_block_header_two": rlp_encoded_block(block_two),
            "signature_block_header_two": keys.Signature(block_two.signature),
        }

        equivocation_report_file_name = (
            f"equivocation_reports_for_proposer_{proposer_address}"
        )

        with open(
            self.report_dir / equivocation_report_file_name, "a"
        ) as equivocation_report_file:
            equivocation_report_file.write(
                EQUIVOCATION_REPORT_TEMPLATE.format(
                    **equivocation_report_template_variables
                )
            )


def validate_skip_rate(ctx, param, value):
    if not 0 <= value <= 1:
        raise click.BadParameter("skip rate must be a value between 0 and 1")

    return value


@click.command()
@click.option(
    "--rpc-uri",
    "-u",
    default=DEFAULT_RPC_URI,
    show_default=True,
    help="URI of the node's JSON RPC server",
)
@click.option(
    "--chain-spec-path",
    "-c",
    required=True,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
    help="path to the chain spec file of the Trustlines blockchain",
)
@click.option(
    "--report-dir",
    "-r",
    default=default_report_dir,
    show_default=True,
    type=click.Path(file_okay=False, writable=True, resolve_path=True),
    help="path to the directory in which misbehavior reports will be created",
)
@click.option(
    "--db-dir",
    "-d",
    default=default_db_dir,
    show_default=True,
    type=click.Path(file_okay=False, writable=True, resolve_path=True),
    help="path to the directory in which the database and application state will be stored",
)
@click.option(
    "--skip-rate",
    "-o",
    default=DEFAULT_ALLOWED_SKIP_RATE,
    show_default=True,
    type=float,
    callback=validate_skip_rate,
    help="maximum rate of assigned steps a validator can skip without being reported as offline",
)
@click.option(
    "--offline-window",
    "-w",
    "offline_window_size_in_seconds",
    default=DEFAULT_OFFLINE_WINDOW_SIZE_IN_SECONDS,
    show_default=True,
    type=click.IntRange(min=0),
    help="size in seconds of the time window considered when determining if validators are offline or not",
)
def main(
    rpc_uri,
    chain_spec_path,
    report_dir,
    db_dir,
    skip_rate,
    offline_window_size_in_seconds,
):
    loop = asyncio.get_event_loop()

    offline_window_size_in_steps = offline_window_size_in_seconds // STEP_DURATION
    app = App(
        rpc_uri=rpc_uri,
        chain_spec_path=Path(chain_spec_path),
        report_dir=Path(report_dir),
        db_dir=Path(db_dir),
        skip_rate=skip_rate,
        offline_window_size=offline_window_size_in_steps,
    )

    loop.add_signal_handler(signal.SIGTERM, app.stop)
    loop.add_signal_handler(signal.SIGINT, app.stop)
    try:
        loop.run_until_complete(app.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
