from atproto_client.models.utils import (
    get_or_create,
    get_model_as_json,
    get_model_as_dict,
)
from atproto import (
    CAR,
    AtUri,
    FirehoseSubscribeReposClient,
    firehose_models,
    models,
    parse_subscribe_repos_message,
)
import json
import glob
from datetime import datetime
from typing import Any, Literal
from tenacity import retry, stop_after_attempt, wait_exponential
from collections import deque

import sinitaivas_live.constants as const
import utils.datetime_utils as dt_utils
import utils.files_storage as fs
import utils.bytes_io as bytes_io
from utils.logging import logger, log_before_retry, log_after_retry


def process_commit(commit: models.ComAtprotoSyncSubscribeRepos.Commit) -> None:
    """Process a commit message from the Firehose stream, by extracting the blocks
    and processing each operation in the commit.

    Parameters:
        commit (models.ComAtprotoSyncSubscribeRepos.Commit): The commit message to process.

    Returns:
        None
    """
    car = CAR.from_bytes(commit.blocks)

    current_utc_time = dt_utils.current_datetime_utc()

    for op in commit.ops:
        with logger.contextualize(op=op):
            _process_op(car, commit, op, current_utc_time)


def _process_op(
    car: CAR,
    commit: models.ComAtprotoSyncSubscribeRepos.Commit,
    op: models.ComAtprotoSyncSubscribeRepos.RepoOp,
    current_utc_time: datetime,
) -> None:
    """Process a single repo operation from the commit.
    This function initializes the commit event, extracts the record from the blocks,
    and saves the commit event to a file.
    It also creates the necessary directories for saving the file.

    Parameters:
        car (CAR): The CAR object containing blocks.
        commit (models.ComAtprotoSyncSubscribeRepos.Commit): The commit message.
        op (models.ComAtprotoSyncSubscribeRepos.RepoOp): The repo operation to process
        current_utc_time (datetime): The current datetime in UTC timezone.

    Returns:
        None
    """
    current_utc_time_str = dt_utils.datetime_as_date_and_hour_str(current_utc_time)
    current_utc_date_str = dt_utils.datetime_as_date_str(current_utc_time)
    prefix = f"{fs.current_dir()}/firehose_stream/{current_utc_date_str}"
    fs.create_dir_if_not_exists(prefix)
    output_filename = f"{prefix}/{current_utc_time_str}.ndjson"

    commit_event = _init_commit_event(commit, op, current_utc_time)
    if not commit_event:
        return
    updated_commit_event = _extract_record_from_blocks(car, op, commit_event)
    _save_commit_event(updated_commit_event, output_filename)


def _save_commit_event(commit_event: dict[str, Any], output_filename: str) -> None:
    """Save the commit event to a JSON file.

    Parameters:
        commit_event (dict[str, Any]): The commit event to save.
        output_filename (str): The output file name.

    Returns:
        None
    """
    try:
        with open(output_filename, "a", encoding="utf-8") as json_file:
            json_file.write(json.dumps(commit_event) + "\n")
    except Exception as e:
        logger.bind(file=output_filename, commit_event=commit_event).error(
            f"Failed to write to file: {e}"
        )


def _extract_record_from_blocks(
    car: CAR,
    op: models.ComAtprotoSyncSubscribeRepos.RepoOp,
    commit_event: dict[str, Any],
) -> dict[str, Any]:
    """Extract the record from the CAR blocks and update the commit event.
    This function retrieves the record from the CAR blocks using the operation's CID,
    converts it to JSON or dictionary format, and updates the commit event with the record data.
    If the record cannot be retrieved or converted, it logs a warning or error.

    Parameters:
        car (CAR): The CAR object.
        op (models.ComAtprotoSyncSubscribeRepos.RepoOp): The operation to process.
        commit_event (dict[str, Any]): The commit event to update.

    Returns:
        dict[str, Any]: The updated commit event.
    """
    model_data = car.blocks.get(op.cid)
    model_instance = get_or_create(model_data, strict=False)
    if not model_instance:
        logger.bind(model_data=model_data).warning("No model instance")
        return commit_event
    try:
        model_json = get_model_as_json(model_instance)
        commit_event.update(json.loads(model_json))
    except Exception as e:
        # this fails for invalid utf-8 bytes
        logger.bind(model_instance=model_instance).warning(
            f"Failed to update commit event with model instance json: {e}"
        )
        try:
            model_dict = get_model_as_dict(model_instance)
            model_dict = bytes_io.convert_bytes_to_str(model_dict)
            commit_event.update(model_dict)
        except Exception as e:
            logger.bind(model_instance=model_instance).error(
                f"Failed to update commit event with model instance dictionary: {e}"
            )
    return commit_event


def _init_commit_event(
    commit: models.ComAtprotoSyncSubscribeRepos.Commit,
    op: models.ComAtprotoSyncSubscribeRepos.RepoOp,
    current_utc_time: datetime,
) -> dict[str, Any]:
    """Initialize a commit event from the commit and operation data.
    This function creates a dictionary representing the commit event,
    including the sequence number, collected time, revision, commit time,
    action, type, URI, author, and CID.

    Parameters:
        commit (models.ComAtprotoSyncSubscribeRepos.Commit): The commit message.
            Represents an update of repository state. Note that empty commits
            are allowed, which include no repo data changes, but an update to
            rev and signature
        op (models.ComAtprotoSyncSubscribeRepos.RepoOp):
            Represents a repo operation, i.e. a mutation of a single record
        current_utc_time (datetime): The current datetime in UTC timezone

    Returns:
        commit_event (dict[str, Any]): The initialized commit event
    """
    try:
        uri = AtUri.from_str(f"at://{commit.repo}/{op.path}")
        return {
            "seq": commit.seq,
            "collected_at": dt_utils.datetime_as_zulu_str(current_utc_time),
            "rev": commit.rev,
            "since": commit.since,
            "commit_time": commit.time,
            "action": op.action,
            "type": uri.collection,  # e.g. "app.bsky.feed.post", same as '$type'
            "uri": str(uri),
            # "uri_host": uri.hostname,
            # "uri_http": uri.http,
            # "uri_origin": uri.origin,
            # "uri_protocol": uri.protocol,
            # "uri_rkey": uri.rkey,
            "author": commit.repo,
            "cid": str(op.cid),
            # "op": op.model_dump(exclude_unset=True),
        }
    except Exception as e:
        logger.bind(uri=uri, cid=op.cid).error(f"Failed to init commit event: {e}")
        return {}


def reset_cursor(client: FirehoseSubscribeReposClient) -> None:
    """Reset the cursor in the client and in cursor file.
    This function sets the cursor to None in the client and removes the
    "streamer" key from the cursor file. It also handles any exceptions
    that may occur while writing to the cursor file.

    Parameters:
        client (FirehoseSubscribeReposClient): The client to reset.

    Returns:
        None
    """
    client.update_params(models.ComAtprotoSyncSubscribeRepos.Params(cursor=None))
    cursor = read_cursor()
    # pop the streamer cursor
    cursor.pop("streamer", None)
    try:
        with open(const.PATH_TO_CURSORS_FILE, "w") as f:
            # dump an empty cursor dictionary
            json.dump(cursor, f)
    except Exception as e:
        logger.bind(file=const.PATH_TO_CURSORS_FILE).error(
            f"Failed to reset cursor: {e}"
        )


def update_cursor(client: FirehoseSubscribeReposClient, cursor_position: int) -> None:
    """Update the cursor position in the client and writes the updated cursor position
    to the cursor file, with the new cursor position and the current UTC time.
    If the cursor file cannot be written, it logs an error.

    Parameters:
        client (FirehoseSubscribeReposClient): The client to update
        cursor_position (int): The cursor value to update

    Returns:
        None
    """
    client.update_params(
        models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor_position)
    )
    cursor = read_cursor()
    cursor["streamer"] = {
        "cursor": cursor_position,
        "updated_at": dt_utils.datetime_as_zulu_str(dt_utils.current_datetime_utc()),
    }
    try:
        with open(const.PATH_TO_CURSORS_FILE, "w") as f:
            json.dump(cursor, f)
    except Exception as e:
        logger.bind(file=const.PATH_TO_CURSORS_FILE).error(
            f"Failed to update cursor file: {e}"
        )


def read_cursor() -> dict[str, Any]:
    """Read the cursor file and return its content.
    If the file does not exist or cannot be read, it logs an error and returns an empty dictionary.

    Returns:
        cursor_streamer (dict[str, Any]): The content of cursor file.
    """
    try:
        with open(const.PATH_TO_CURSORS_FILE, "r") as f:
            return json.load(f)  # type: ignore
    except Exception as e:
        logger.bind(file=const.PATH_TO_CURSORS_FILE).error(
            f"Failed to read cursor file: {e}"
        )
        return {}


def read_last_seq_from_file() -> int:
    """Read the last sequence value from the latest ndjson file in the firehose_stream directory.
    This function searches for all ndjson files in the firehose_stream directory,
    sorts them by name to find the latest file, and reads the last line of that file.
    If no ndjson files are found or if the last line cannot be read, returns 0.

    Returns:
        seq (int): The last sequence value.
    """
    # get all ndjson files under firehose_stream
    json_files = sorted(
        file
        for file in glob.glob(
            f"{fs.current_dir()}/firehose_stream/**/*.ndjson", recursive=False
        )
    )
    if not json_files:
        logger.warning("No ndjson files found")
        return 0

    # max by name, which is the latest date and hour
    latest_file = json_files[-1]

    try:
        # read last line from the latest json file
        with open(latest_file, "r") as file:
            last_line = deque(file, maxlen=1)
            if last_line:
                last_line_json = json.loads(last_line[0])
                return int(last_line_json["seq"])
            logger.bind(last_line=last_line).warning("No content in the latest line")
            return 0

    except Exception as e:
        logger.bind(latest_file=latest_file).error(
            f"Failed to read last seq from file: {e}"
        )
        return 0


def get_fresh_client() -> FirehoseSubscribeReposClient:
    """Start a Firehose Subscriber client without considering the cursor position.

    Returns:
        FirehoseSubscribeReposClient: The client instance.
    """
    return FirehoseSubscribeReposClient(base_uri="wss://bsky.network/xrpc")


def resume_streamer() -> FirehoseSubscribeReposClient:
    """Resume the streamer from the last known cursor position.
    The cursor position is read from the cursor file.
    If the cursor position is not found, it reads the last sequence from the latest ndjson file.

    Returns:
        FirehoseSubscribeReposClient: The client instance.
    """
    client = get_fresh_client()
    cursor_position = read_cursor().get("streamer", {}).get("cursor")
    if not cursor_position:
        last_seq = read_last_seq_from_file()
        cursor_position = last_seq
    client.update_params(
        models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor_position)
    )
    logger.info(f"Resuming streamer from cursor: {cursor_position}")
    return client


def start(client: FirehoseSubscribeReposClient) -> FirehoseSubscribeReposClient:
    """Start the subscription to the Firehose and process incoming messages.

    Returns:
        FirehoseSubscribeReposClient: The client instance
    """

    def on_message_callback(message: firehose_models.MessageFrame) -> None:
        """Handle incoming messages from the Firehose stream.
        This function parses the incoming message, processes the commit if valid,
        and updates the cursor position in the client.

        Parameters:
            message (firehose_models.MessageFrame): The incoming message frame

        Returns:
            None
        """
        commit = parse_subscribe_repos_message(message)
        if (
            not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit)
            or not commit.blocks
        ):
            logger.bind(commit=commit).warning("Invalid commit")
            return

        process_commit(commit)
        update_cursor(client, commit.seq)

    def on_callback_error_callback(error: BaseException) -> None:
        """Callback to handle errors encountered during message processing.

        Parameters:
            error (BaseException): The error encountered

        Returns:
            None
        """
        logger.error(error)

    client.start(on_message_callback, on_callback_error_callback)
    return client


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    before=log_before_retry,
    after=log_after_retry,
)
def start_with_retry(
    client: FirehoseSubscribeReposClient,
) -> FirehoseSubscribeReposClient:
    return start(client)


def streamer_main(mode: Literal["fresh", "resume"]) -> None:
    """Main function to run the streamer.

    Parameters:
        mode (str): Mode to run the streamer [fresh/resume].
    Returns:
        None
    """
    if mode == "fresh":
        client = get_fresh_client()
        reset_cursor(client)
    else:
        client = resume_streamer()

    try:
        client = start_with_retry(client)
    except Exception as e:
        logger.error(f"Cannot recover from failures: {e}")
