from unittest.mock import patch, MagicMock
from datetime import datetime

from sinitaivas_live.streamer import (
    process_commit,
    _process_op,
    _save_commit_event,
    _init_commit_event,
    reset_cursor,
    update_cursor,
    read_cursor,
    streamer_main,
)


@patch("sinitaivas_live.streamer._process_op")
@patch("sinitaivas_live.streamer.dt_utils.current_datetime_utc")
@patch("sinitaivas_live.streamer.CAR.from_bytes")
def test_process_commit(mock_from_bytes, mock_current_datetime_utc, mock_process_op):
    commit = MagicMock()
    mock_current_datetime_utc.return_value = datetime(2023, 1, 1)
    process_commit(commit)
    mock_from_bytes.assert_called_once_with(commit.blocks)
    assert mock_process_op.call_count == len(commit.ops)


@patch("sinitaivas_live.streamer.fs.create_dir_if_not_exists")
@patch("sinitaivas_live.streamer._save_commit_event")
@patch("sinitaivas_live.streamer._extract_record_from_blocks")
@patch("sinitaivas_live.streamer._init_commit_event")
@patch("sinitaivas_live.streamer.dt_utils.current_datetime_utc")
def test_process_op(
    mock_current_datetime_utc,
    mock_init_commit_event,
    mock_extract_record_from_blocks,
    mock_save_commit_event,
    mock_create_dir_if_not_exists,
):
    car = MagicMock()
    commit = MagicMock()
    op = MagicMock()
    mock_current_datetime_utc.return_value = datetime(2023, 1, 1)
    mock_init_commit_event.return_value = {"key": "value"}
    _process_op(car, commit, op, datetime(2023, 1, 1))
    mock_create_dir_if_not_exists.assert_called_once()
    mock_save_commit_event.assert_called_once()


@patch("sinitaivas_live.streamer.json.dumps")
@patch("sinitaivas_live.streamer.logger")
def test_save_commit_event(mock_logger, mock_json_dumps):
    commit_event = {"key": "value"}
    output_filename = "test.ndjson"
    mock_json_dumps.return_value = '{"key": "value"}'
    _save_commit_event(commit_event, output_filename)
    mock_json_dumps.assert_called_once_with(commit_event)
    mock_logger.bind.assert_not_called()


@patch("sinitaivas_live.streamer.AtUri.from_str")
@patch("sinitaivas_live.streamer.dt_utils.datetime_as_zulu_str")
def test_init_commit_event(mock_datetime_as_zulu_str, mock_from_str):
    commit = MagicMock()
    op = MagicMock()
    current_utc_time = datetime(2023, 1, 1)
    mock_from_str.return_value = MagicMock(collection="collection")
    mock_datetime_as_zulu_str.return_value = "2023-01-01T00:00:00Z"
    commit_event = _init_commit_event(commit, op, current_utc_time)
    assert commit_event["seq"] == commit.seq


@patch("sinitaivas_live.streamer.read_cursor")
@patch("sinitaivas_live.streamer.logger")
def test_reset_cursor(mock_logger, mock_read_cursor):
    client = MagicMock()
    mock_read_cursor.return_value = {"streamer": 123}
    reset_cursor(client)
    client.update_params.assert_called_once()
    mock_logger.bind.assert_not_called()


@patch("sinitaivas_live.streamer.read_cursor")
@patch("sinitaivas_live.streamer.logger")
def test_update_cursor(mock_logger, mock_read_cursor):
    client = MagicMock()
    mock_read_cursor.return_value = {}
    update_cursor(client, 123)
    client.update_params.assert_called_once()
    mock_logger.bind.assert_not_called()


@patch("sinitaivas_live.streamer.json.load")
@patch("sinitaivas_live.streamer.logger")
def test_read_cursor(mock_logger, mock_json_load):
    mock_json_load.return_value = {"key": "value"}
    cursor = read_cursor()
    assert cursor["key"] == "value"
    mock_logger.bind.assert_not_called()


@patch("sinitaivas_live.streamer.start_with_retry")
@patch("sinitaivas_live.streamer.reset_cursor")
@patch("sinitaivas_live.streamer.get_fresh_client")
@patch("sinitaivas_live.streamer.resume_streamer")
@patch("sinitaivas_live.streamer.logger")
def test_streamer_main(
    mock_logger,
    mock_resume_streamer,
    mock_get_fresh_client,
    mock_reset_cursor,
    mock_start_with_retry,
):
    mock_get_fresh_client.return_value = MagicMock()
    streamer_main("fresh")
    mock_reset_cursor.assert_called_once()
    mock_start_with_retry.assert_called_once()
    streamer_main("resume")
    mock_resume_streamer.assert_called_once()
    mock_start_with_retry.assert_called()
