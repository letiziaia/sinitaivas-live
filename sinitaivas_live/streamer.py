from atproto import (
    FirehoseSubscribeReposClient,
    firehose_models,
    models,
    parse_subscribe_repos_message,
)
from typing import Literal
from tenacity import retry, stop_after_attempt, wait_exponential

import sinitaivas_live.cursor as cursor
import sinitaivas_live.parser as parser
from utils.logging import logger, log_before_retry, log_after_retry


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
    cursor_position = cursor.read_cursor().get("streamer", {}).get("cursor")
    if not cursor_position:
        last_seq = cursor.read_last_seq_from_file()
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

        parser.process_commit(commit)
        cursor.update_cursor(client, commit.seq)

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
        cursor.reset_cursor(client)
    else:
        client = resume_streamer()

    try:
        client = start_with_retry(client)
    except Exception as e:
        logger.error(f"Cannot recover from failures: {e}")
