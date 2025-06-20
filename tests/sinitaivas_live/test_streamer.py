from unittest.mock import patch, MagicMock
from atproto import models, FirehoseSubscribeReposClient

from sinitaivas_live.streamer import (
    get_fresh_client,
    resume_streamer,
    start,
    streamer_main,
)


def test_get_fresh_client():
    client = get_fresh_client()
    # Check that the returned object is an instance of FirehoseSubscribeReposClient
    assert isinstance(client, FirehoseSubscribeReposClient)


@patch("sinitaivas_live.streamer.logger")
@patch("sinitaivas_live.streamer.cursor.read_last_seq_from_file")
@patch("sinitaivas_live.streamer.cursor.read_cursor")
@patch("sinitaivas_live.streamer.get_fresh_client")
def test_resume_streamer_reads_cursor_and_sets_params(
    mock_get_fresh_client,
    mock_read_cursor,
    mock_read_last_seq_from_file,
    mock_logger,
):
    # Arrange: cursor file has a valid cursor
    mock_client = MagicMock()
    mock_get_fresh_client.return_value = mock_client
    mock_read_cursor.return_value = {"streamer": {"cursor": 42}}
    # Act
    result = resume_streamer()
    # Assert
    mock_get_fresh_client.assert_called_once()
    mock_read_cursor.assert_called_once()
    mock_read_last_seq_from_file.assert_not_called()
    mock_client.update_params.assert_called_once()
    args, kwargs = mock_client.update_params.call_args
    assert args[0].cursor == 42
    mock_logger.info.assert_called_with("Resuming streamer from cursor: 42")
    assert result == mock_client


@patch("sinitaivas_live.streamer.logger")
@patch("sinitaivas_live.streamer.cursor.read_last_seq_from_file")
@patch("sinitaivas_live.streamer.cursor.read_cursor")
@patch("sinitaivas_live.streamer.get_fresh_client")
def test_resume_streamer_reads_last_seq_if_no_cursor(
    mock_get_fresh_client,
    mock_read_cursor,
    mock_read_last_seq_from_file,
    mock_logger,
):
    # Arrange: cursor file has no cursor, fallback to last seq
    mock_client = MagicMock()
    mock_get_fresh_client.return_value = mock_client
    mock_read_cursor.return_value = {"streamer": {}}
    mock_read_last_seq_from_file.return_value = 99
    # Act
    result = resume_streamer()
    # Assert
    mock_get_fresh_client.assert_called_once()
    mock_read_cursor.assert_called_once()
    mock_read_last_seq_from_file.assert_called_once()
    mock_client.update_params.assert_called_once()
    args, kwargs = mock_client.update_params.call_args
    assert args[0].cursor == 99
    mock_logger.info.assert_called_with("Resuming streamer from cursor: 99")
    assert result == mock_client


@patch("sinitaivas_live.streamer.logger")
@patch("sinitaivas_live.streamer.cursor.read_last_seq_from_file")
@patch("sinitaivas_live.streamer.cursor.read_cursor")
@patch("sinitaivas_live.streamer.get_fresh_client")
def test_resume_streamer_handles_missing_streamer_key(
    mock_get_fresh_client,
    mock_read_cursor,
    mock_read_last_seq_from_file,
    mock_logger,
):
    # Arrange: cursor file missing 'streamer' key
    mock_client = MagicMock()
    mock_get_fresh_client.return_value = mock_client
    mock_read_cursor.return_value = {}
    mock_read_last_seq_from_file.return_value = 1234
    # Act
    result = resume_streamer()
    # Assert
    mock_get_fresh_client.assert_called_once()
    mock_read_cursor.assert_called_once()
    mock_read_last_seq_from_file.assert_called_once()
    mock_client.update_params.assert_called_once()
    args, kwargs = mock_client.update_params.call_args
    assert args[0].cursor == 1234
    mock_logger.info.assert_called_with("Resuming streamer from cursor: 1234")
    assert result == mock_client


@patch("sinitaivas_live.streamer.cursor.update_cursor")
@patch("sinitaivas_live.streamer.parser.process_commit")
@patch("sinitaivas_live.streamer.logger")
@patch("sinitaivas_live.streamer.parse_subscribe_repos_message")
def test_start_processes_valid_commit(
    mock_parse_subscribe_repos_message,
    mock_logger,
    mock_process_commit,
    mock_update_cursor,
):
    # Arrange
    mock_client = MagicMock()
    mock_commit = MagicMock(spec=models.ComAtprotoSyncSubscribeRepos.Commit)
    mock_commit.blocks = True
    mock_commit.seq = 123

    # Simulate a valid commit object
    mock_parse_subscribe_repos_message.return_value = mock_commit

    # Get the on_message_callback by calling start
    start(mock_client)
    # Extract the callback passed to client.start
    on_message_callback = mock_client.start.call_args[0][0]

    # Act
    on_message_callback("fake_message")

    # Assert
    mock_parse_subscribe_repos_message.assert_called_once_with("fake_message")
    mock_process_commit.assert_called_once_with(mock_commit)
    mock_update_cursor.assert_called_once_with(mock_client, 123)
    mock_logger.bind.assert_not_called()  # Should not log warning for valid commit


@patch("sinitaivas_live.streamer.cursor.update_cursor")
@patch("sinitaivas_live.streamer.parser.process_commit")
@patch("sinitaivas_live.streamer.logger")
@patch("sinitaivas_live.streamer.parse_subscribe_repos_message")
def test_start_invalid_commit_logs_warning(
    mock_parse_subscribe_repos_message,
    mock_logger,
    mock_process_commit,
    mock_update_cursor,
):
    # Arrange
    mock_client = MagicMock()
    # Simulate an invalid commit (not instance of Commit or no blocks)
    mock_parse_subscribe_repos_message.return_value = "not_a_commit"

    start(mock_client)
    on_message_callback = mock_client.start.call_args[0][0]

    # Act
    on_message_callback("fake_message")

    # Assert
    mock_logger.bind.return_value.warning.assert_called_once()
    mock_process_commit.assert_not_called()
    mock_update_cursor.assert_not_called()


@patch("sinitaivas_live.streamer.logger")
def test_start_on_callback_error_callback_logs_error(mock_logger):
    mock_client = MagicMock()
    start(mock_client)
    # Extract the error callback
    on_callback_error_callback = mock_client.start.call_args[0][1]
    error = Exception("test error")
    on_callback_error_callback(error)
    mock_logger.error.assert_called_with(error)


@patch("sinitaivas_live.streamer.start_with_retry")
@patch("sinitaivas_live.streamer.cursor.reset_cursor")
@patch("sinitaivas_live.streamer.get_fresh_client")
@patch("sinitaivas_live.streamer.resume_streamer")
def test_streamer_main_fresh(
    mock_resume_streamer,
    mock_get_fresh_client,
    mock_reset_cursor,
    mock_start_with_retry,
):
    mock_get_fresh_client.return_value = MagicMock()
    streamer_main("fresh")
    mock_get_fresh_client.assert_called_once()
    mock_reset_cursor.assert_called_once()
    mock_start_with_retry.assert_called_once()
    mock_start_with_retry.assert_called_once()


@patch("sinitaivas_live.streamer.start_with_retry")
@patch("sinitaivas_live.streamer.cursor.reset_cursor")
@patch("sinitaivas_live.streamer.get_fresh_client")
@patch("sinitaivas_live.streamer.resume_streamer")
def test_streamer_main_resume(
    mock_resume_streamer,
    mock_get_fresh_client,
    mock_reset_cursor,
    mock_start_with_retry,
):
    mock_get_fresh_client.return_value = MagicMock()
    streamer_main("resume")
    mock_get_fresh_client.assert_not_called()
    mock_reset_cursor.assert_not_called()
    mock_resume_streamer.assert_called_once()
    mock_start_with_retry.assert_called_once()
