from unittest.mock import patch, MagicMock

from sinitaivas_live.cursor import (
    reset_cursor,
    update_cursor,
    read_cursor,
    read_last_seq_from_file,
)


@patch("sinitaivas_live.cursor.read_cursor")
@patch("sinitaivas_live.cursor.logger")
def test_reset_cursor(mock_logger, mock_read_cursor):
    """Test the reset_cursor function."""
    client = MagicMock()
    mock_read_cursor.return_value = {"streamer": 123}
    reset_cursor(client)
    client.update_params.assert_called_once()
    mock_logger.error.assert_not_called()


@patch("sinitaivas_live.cursor.read_cursor")
@patch("sinitaivas_live.cursor.logger")
def test_update_cursor(mock_logger, mock_read_cursor):
    client = MagicMock()
    mock_read_cursor.return_value = {}
    update_cursor(client, 123)
    client.update_params.assert_called_once()
    mock_logger.error.assert_not_called()


@patch("sinitaivas_live.cursor.json.load")
@patch("sinitaivas_live.cursor.logger")
def test_read_cursor(mock_logger, mock_json_load):
    mock_json_load.return_value = {"key": "value"}
    cursor = read_cursor()
    assert cursor["key"] == "value"
    mock_logger.error.assert_not_called()


@patch("sinitaivas_live.cursor.open")
@patch("sinitaivas_live.cursor.json.dump")
def test_read_cursor_file_not_found(mock_json_dump, mock_open):
    """Test reading cursor file when it does not exist."""
    mock_open.side_effect = FileNotFoundError
    cursor = read_cursor()
    assert cursor == {}
    mock_json_dump.assert_not_called()


@patch("sinitaivas_live.cursor.open")
@patch("sinitaivas_live.cursor.json.dump")
def test_read_cursor_file_error(mock_json_dump, mock_open):
    """Test reading cursor file when an error occurs."""
    mock_open.side_effect = Exception("Error reading file")
    cursor = read_cursor()
    assert cursor == {}
    mock_json_dump.assert_not_called()


@patch("sinitaivas_live.cursor.open")
@patch("sinitaivas_live.cursor.json.dump")
def test_update_cursor_file_error(mock_json_dump, mock_open):
    """Test updating cursor file when an error occurs."""
    mock_open.side_effect = Exception("Error writing file")
    client = MagicMock()
    update_cursor(client, 123)
    client.update_params.assert_called_once()
    mock_json_dump.assert_not_called()


@patch("sinitaivas_live.cursor.open")
@patch("sinitaivas_live.cursor.deque")
@patch("sinitaivas_live.cursor._get_json_files")
def test_read_last_seq_from_file(mock_get_json_files, mock_deque, mock_open):
    """Test reading the last sequence from the latest ndjson file."""
    mock_get_json_files.return_value = ["path/to/last_file.ndjson"]
    mock_deque.return_value = ["""{"seq": 456}"""]
    last_seq = read_last_seq_from_file()
    assert last_seq == 456
    mock_open.assert_called_once_with("path/to/last_file.ndjson", "r")


@patch("sinitaivas_live.cursor.open")
@patch("sinitaivas_live.cursor._get_json_files")
def test_read_last_seq_from_file_not_found(mock_get_json_files, mock_open):
    """Test reading last sequence when the file does not exist."""
    mock_get_json_files.return_value = ["non_existent_file.ndjson"]
    mock_open.side_effect = FileNotFoundError
    last_seq = read_last_seq_from_file()
    assert last_seq == 0


@patch("sinitaivas_live.cursor.open")
@patch("sinitaivas_live.cursor._get_json_files")
def test_read_last_seq_from_file_error(mock_get_json_files, mock_open):
    """Test reading last sequence when an error occurs."""
    mock_get_json_files.return_value = ["path/to/last_file.ndjson"]
    mock_open.side_effect = Exception("Error reading file")
    last_seq = read_last_seq_from_file()
    assert last_seq == 0


@patch("sinitaivas_live.cursor._get_json_files")
def test_read_last_seq_from_file_no_files(mock_get_json_files):
    """Test reading last sequence when no ndjson files are found."""
    mock_get_json_files.return_value = []
    last_seq = read_last_seq_from_file()
    assert last_seq == 0
