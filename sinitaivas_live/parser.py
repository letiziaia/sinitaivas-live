from atproto_client.models.utils import (
    get_or_create,
    get_model_as_json,
    get_model_as_dict,
)
from atproto import (
    CAR,
    AtUri,
    models,
)
import json
from typing import Any

import utils.datetime_utils as dt_utils
import utils.files_storage as fs
import utils.bytes_io as bytes_io
from utils.logging import logger


def process_commit(commit: models.ComAtprotoSyncSubscribeRepos.Commit) -> None:
    """Process a commit message from the Firehose stream, by extracting the blocks
    and processing each operation in the commit.

    Parameters:
        commit (models.ComAtprotoSyncSubscribeRepos.Commit): The commit message to process.

    Returns:
        None
    """
    for op in commit.ops:
        with logger.contextualize(op=op):
            _process_op(commit, op)


def _process_op(
    commit: models.ComAtprotoSyncSubscribeRepos.Commit,
    op: models.ComAtprotoSyncSubscribeRepos.RepoOp,
) -> None:
    """Process a single repo operation from the commit.
    This function initializes the commit event, extracts the record from the blocks,
    and saves the commit event to a file.
    It also creates the necessary directories for saving the file.

    Parameters:
        commit (models.ComAtprotoSyncSubscribeRepos.Commit): The commit message.
        op (models.ComAtprotoSyncSubscribeRepos.RepoOp): The repo operation to process

    Returns:
        None
    """
    # time and date for the collected_at field, and output dir and filename
    current_utc_time = dt_utils.current_datetime_utc()
    current_utc_time_str = dt_utils.datetime_as_date_and_hour_str(current_utc_time)
    current_utc_date_str = dt_utils.datetime_as_date_str(current_utc_time)

    # output directory and filename
    prefix = f"{fs.current_dir()}/firehose_stream/{current_utc_date_str}"
    fs.create_dir_if_not_exists(prefix)
    output_filename = f"{prefix}/{current_utc_time_str}.ndjson"

    commit_event = _init_commit_event(commit)
    if not commit_event:
        return

    commit_event = _add_current_utc_time_to_commit_event(
        commit_event, current_utc_time_str
    )
    commit_event = _update_commit_event_with_op(commit_event, op)

    uri = AtUri.from_str(f"at://{commit.repo}/{op.path}")
    commit_event = _update_commit_event_with_uri(commit_event, uri)

    car = CAR.from_bytes(commit.blocks)
    commit_event = _extract_record_from_blocks(commit_event, car, op)
    _save_commit_event(commit_event, output_filename)


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
    commit_event: dict[str, Any],
    car: CAR,
    op: models.ComAtprotoSyncSubscribeRepos.RepoOp,
) -> dict[str, Any]:
    """Extract the record from the CAR blocks and update the commit event.
    This function retrieves the record from the CAR blocks using the operation's CID,
    converts it to JSON or dictionary format, and updates the commit event with the record data.
    If the record cannot be retrieved or converted, it logs a warning or error.

    Parameters:
        commit_event (dict[str, Any]): The commit event to update.
        car (CAR): The CAR object.
        op (models.ComAtprotoSyncSubscribeRepos.RepoOp): The operation to process.

    Returns:
        commit_event (dict[str, Any]): The updated commit event.
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
) -> dict[str, Any]:
    """Initialize a commit event from the commit data.
    This function creates a dictionary representing the commit event,
    including the sequence number, revision, commit time.

    Parameters:
        commit (models.ComAtprotoSyncSubscribeRepos.Commit): The commit message.
            Represents an update of repository state. Note that empty commits
            are allowed, which include no repo data changes, but an update to
            rev and signature

    Returns:
        commit_event (dict[str, Any]): The initialized commit event
    """
    try:
        return {
            "author": commit.repo,
            "rev": commit.rev,
            "seq": commit.seq,
            "since": commit.since,
            "commit_time": commit.time,
        }
    except Exception as e:
        logger.bind(commit=commit).error(f"Failed to init commit event: {e}")
        return {}


def _add_current_utc_time_to_commit_event(
    commit_event: dict[str, Any],
    current_utc_time_str: str,
) -> dict[str, Any]:
    """Add the current UTC time to the commit event.
    This function adds the current UTC time as a 'collected_at' field to the commit event.

    Parameters:
        commit_event (dict[str, Any]): The commit event to update.
        current_utc_time_str (str): The current UTC time as a string in Zulu format.

    Returns:
        commit_event (dict[str, Any]): The updated commit event with 'collected_at' field.
    """
    commit_event["collected_at"] = current_utc_time_str
    return commit_event


def _update_commit_event_with_op(
    commit_event: dict[str, Any],
    op: models.ComAtprotoSyncSubscribeRepos.RepoOp,
) -> dict[str, Any]:
    """Update the commit event with operation action, type, and CID.

    Parameters:
        commit_event (dict[str, Any]): The commit event to update.
        op (models.ComAtprotoSyncSubscribeRepos.RepoOp): The repo operation to add.

    Returns:
        commit_event (dict[str, Any]): The updated commit event with operation data.
    """
    try:
        commit_event.update(
            {
                "action": op.action,
                "path": op.path,
                "cid": str(op.cid),
            }
        )
    except Exception as e:
        logger.bind(op=op).error(f"Failed to add op to commit event: {e}")
    return commit_event


def _update_commit_event_with_uri(
    commit_event: dict[str, Any],
    uri: AtUri,
) -> dict[str, Any]:
    """Update the commit event with the URI collection type, full HTTP URL, and rkey.

    Parameters:
        commit_event (dict[str, Any]): The commit event to update.
        uri (AtUri): The URI to add to the commit event.

    Returns:
        commit_event (dict[str, Any]): The updated commit event with URI data.
    """
    try:
        commit_event.update(
            {
                "type": uri.collection,  # e.g. "app.bsky.feed.post", same as '$type'
                # "uri_host": uri.hostname,  # same as commit.repo (author)
                "uri": uri.http,  # full http URL of the URI as a string
                # "uri_origin": uri.origincommit,  # the origin commit of the URI
                # "uri_protocol": uri.protocol,  # e.g. "at://"
                "uri_rkey": uri.rkey,  # the rkey of the URI
                # "uri_search_params": uri.search,  # the search parameters of the URI
            }
        )
    except Exception as e:
        logger.bind(uri=uri).error(f"Failed to add URI to commit event: {e}")
    return commit_event
