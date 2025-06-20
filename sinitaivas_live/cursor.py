from atproto import (
    FirehoseSubscribeReposClient,
    models,
)
import json
import glob
from typing import Any
from collections import deque

import sinitaivas_live.constants as const
import utils.datetime_utils as dt_utils
import utils.files_storage as fs
from utils.logging import logger


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
    json_files = _get_json_files()
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


def _get_json_files() -> list[str]:
    """Find all files with the .ndjson extension in the firehose_stream directory
    and return them sorted by name.

    Returns:
        json_files (list[str]): A sorted list of file paths to ndjson files.
    """
    # get all ndjson files under firehose_stream
    return sorted(
        file
        for file in glob.glob(
            f"{fs.current_dir()}/firehose_stream/**/*.ndjson", recursive=False
        )
    )
