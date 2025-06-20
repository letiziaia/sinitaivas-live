from unittest.mock import patch, MagicMock, PropertyMock

from sinitaivas_live.parser import (
    process_commit,
    _process_op,
    _save_commit_event,
    _init_commit_event,
    _extract_record_from_blocks,
    _add_current_utc_time_to_commit_event,
    _update_commit_event_with_op,
    _update_commit_event_with_uri,
)


@patch("sinitaivas_live.parser._process_op")
def test_process_commit(mock_process_op):
    # setup commit with multiple ops
    commit = MagicMock()
    commit.ops = [MagicMock() for _ in range(5)]
    process_commit(commit)
    assert mock_process_op.call_count == len(commit.ops)


@patch("sinitaivas_live.parser._init_commit_event")
@patch("sinitaivas_live.parser._update_commit_event_with_op")
@patch("sinitaivas_live.parser._update_commit_event_with_uri")
@patch("sinitaivas_live.parser.CAR")
@patch("sinitaivas_live.parser._extract_record_from_blocks")
@patch("sinitaivas_live.parser._save_commit_event")
@patch("sinitaivas_live.parser.AtUri")
@patch("sinitaivas_live.parser.fs")
def test_process_op_happy_path(
    mock_fs,
    mock_AtUri,
    mock_save_commit_event,
    mock_extract_record_from_blocks,
    mock_CAR,
    mock_update_commit_event_with_uri,
    mock_update_commit_event_with_op,
    mock_init_commit_event,
):
    # Setup
    commit = MagicMock()
    op = MagicMock()
    commit.repo = "repo"
    op.path = "some/path"
    commit.blocks = b"bytes"
    mock_fs.current_dir.return_value = "/tmp"
    mock_init_commit_event.return_value = {"init": "event"}
    mock_update_commit_event_with_op.return_value = {
        "init": "event",
        "collected_at": "2023-01-01T00",
        "action": "create",
    }
    mock_uri = MagicMock()
    mock_AtUri.from_str.return_value = mock_uri
    mock_update_commit_event_with_uri.return_value = {"final": "event"}
    mock_car = MagicMock()
    mock_CAR.from_bytes.return_value = mock_car
    mock_extract_record_from_blocks.return_value = {"final": "event"}

    # Call
    _process_op(commit, op)

    # Assert
    mock_fs.create_dir_if_not_exists.assert_called_once()
    mock_save_commit_event.assert_called_once()
    mock_CAR.from_bytes.assert_called_once_with(commit.blocks)
    mock_AtUri.from_str.assert_called_once_with(f"at://{commit.repo}/{op.path}")


@patch("sinitaivas_live.parser._init_commit_event", return_value=None)
@patch("sinitaivas_live.parser.logger")
def test_process_op_no_commit_event(mock_logger, mock_init_commit_event):
    commit = MagicMock()
    op = MagicMock()

    _process_op(commit, op)

    # Should return early, so nothing else called
    assert mock_init_commit_event.called


@patch("sinitaivas_live.parser.json.dumps")
@patch("sinitaivas_live.parser.logger")
def test_save_commit_event(mock_logger, mock_json_dumps):
    commit_event = {"key": "value"}
    output_filename = "test.ndjson"
    mock_json_dumps.return_value = '{"key": "value"}'
    _save_commit_event(commit_event, output_filename)
    mock_json_dumps.assert_called_once_with(commit_event)
    mock_logger.bind.assert_not_called()


@patch("sinitaivas_live.parser.logger")
def test_save_commit_event_fail(mock_logger):
    commit_event = {"key": "value"}
    output_filename = "test.ndjson"

    # Instead of patching open directly, use a proper context manager mock
    with patch(
        "sinitaivas_live.parser.open", side_effect=Exception("File write error")
    ) as mock_open:

        _save_commit_event(commit_event, output_filename)

        # Check that open was called with the right arguments
        mock_open.assert_called_once_with(output_filename, "a", encoding="utf-8")

        # Check that logger was called correctly
        mock_logger.bind.assert_called_once_with(
            file=output_filename, commit_event=commit_event
        )
        mock_logger.bind.return_value.error.assert_called_once_with(
            "Failed to write to file: File write error"
        )


def test_init_commit_event():
    # setup a mock commit object
    mock_commit = MagicMock()
    mock_commit.seq = 12345
    mock_commit.repo = "repo_id"
    mock_commit.rev = "revision_id"
    mock_commit.since = "since_id"
    mock_commit.time = "1999-01-01T23:59:59.123Z"

    expected_keys = [
        "author",
        "rev",
        "seq",
        "since",
        "commit_time",
    ]

    commit_event = _init_commit_event(mock_commit)
    assert isinstance(commit_event, dict)
    assert all(key in commit_event for key in expected_keys)
    assert commit_event["author"] == mock_commit.repo
    assert commit_event["rev"] == mock_commit.rev
    assert commit_event["seq"] == mock_commit.seq
    assert commit_event["since"] == mock_commit.since
    assert commit_event["commit_time"] == mock_commit.time


@patch("sinitaivas_live.parser.logger")
def test_init_commit_event_fail(mock_logger):
    # setup a mock commit object with missing fields
    mock_commit = MagicMock()
    type(mock_commit).repo = PropertyMock(side_effect=Exception("Missing repo field"))

    commit_event = _init_commit_event(mock_commit)
    assert isinstance(commit_event, dict)
    assert commit_event == {}
    # logger error should be called
    mock_logger.bind.assert_called_once_with(commit=mock_commit)


def test_add_current_utc_time_to_commit_event():
    commit_event = {"key": "value"}
    current_utc_time_str = "2023-01-01T00:00:00Z"
    updated_commit_event = _add_current_utc_time_to_commit_event(
        commit_event, current_utc_time_str
    )
    assert updated_commit_event["collected_at"] == current_utc_time_str
    assert updated_commit_event["key"] == "value"


@patch("sinitaivas_live.parser.get_or_create")
@patch("sinitaivas_live.parser.get_model_as_json")
@patch("sinitaivas_live.parser.get_model_as_dict")
@patch("sinitaivas_live.parser.logger")
def test_extract_record_from_blocks_success(
    mock_logger,
    mock_get_model_as_dict,
    mock_get_model_as_json,
    mock_get_or_create,
):
    # Setup
    commit_event = {"existing": "data"}
    car = MagicMock()
    op = MagicMock()
    op.cid = "cid1"
    model_data = {"foo": "bar"}
    car.blocks.get.return_value = model_data
    model_instance = MagicMock()
    mock_get_or_create.return_value = model_instance
    mock_get_model_as_json.return_value = '{"new_key": "new_value"}'

    # Call
    result = _extract_record_from_blocks(commit_event.copy(), car, op)

    # Assert
    assert "new_key" in result
    assert result["new_key"] == "new_value"
    mock_get_model_as_json.assert_called_once_with(model_instance)
    mock_logger.bind.assert_not_called()
    mock_get_model_as_dict.assert_not_called()


@patch("sinitaivas_live.parser.get_or_create")
@patch("sinitaivas_live.parser.get_model_as_json", side_effect=Exception("bad json"))
@patch("sinitaivas_live.parser.get_model_as_dict")
@patch("sinitaivas_live.parser.logger")
@patch("sinitaivas_live.parser.bytes_io")
def test_extract_record_from_blocks_json_fail_dict_success(
    mock_bytes_io,
    mock_logger,
    mock_get_model_as_dict,
    mock_get_model_as_json,
    mock_get_or_create,
):
    commit_event = {"existing": "data"}
    car = MagicMock()
    op = MagicMock()
    op.cid = "cid1"
    car.blocks.get.return_value = {"foo": "bar"}
    model_instance = MagicMock()
    mock_get_or_create.return_value = model_instance

    # make mock_get_model_as_dict return a dict with bytes
    mock_get_model_as_dict.return_value = {"dict_key": b"bytes_value"}
    mock_bytes_io.convert_bytes_to_str.return_value = {"dict_key": "str_value"}
    mock_get_model_as_dict.return_value = {"dict_key": b"bytes_value"}
    mock_bytes_io.convert_bytes_to_str.return_value = {"dict_key": "str_value"}

    result = _extract_record_from_blocks(commit_event.copy(), car, op)

    assert "dict_key" in result
    assert result["dict_key"] == "str_value"
    mock_logger.bind.return_value.warning.assert_called_once()
    mock_logger.bind.return_value.error.assert_not_called()


@patch("sinitaivas_live.parser.get_or_create")
@patch("sinitaivas_live.parser.logger")
def test_extract_record_from_blocks_no_model_instance(mock_logger, mock_get_or_create):
    commit_event = {"existing": "data"}
    car = MagicMock()
    op = MagicMock()
    op.cid = "cid1"
    car.blocks.get.return_value = {"foo": "bar"}
    mock_get_or_create.return_value = None

    result = _extract_record_from_blocks(commit_event.copy(), car, op)

    assert result == commit_event
    mock_logger.bind.assert_called_once()
    mock_logger.bind.return_value.warning.assert_called_once_with("No model instance")


def test_update_commit_event_with_op():
    commit_event = {"foo": "bar"}
    op = MagicMock()
    op.action = "create"
    op.path = "some/path"
    op.cid = "cid123"

    updated = _update_commit_event_with_op(commit_event.copy(), op)
    assert updated["action"] == "create"
    assert updated["path"] == "some/path"
    assert updated["cid"] == "cid123"
    assert updated["foo"] == "bar"


@patch("sinitaivas_live.parser.logger")
def test_update_commit_event_with_op_exception(mock_logger):
    commit_event = {"foo": "bar"}
    op = MagicMock()
    # Simulate exception when accessing op.action
    type(op).action = property(lambda self: (_ for _ in ()).throw(Exception("fail")))
    type(op).path = property(lambda self: "some/path")
    type(op).cid = property(lambda self: "cid123")

    result = _update_commit_event_with_op(commit_event.copy(), op)
    # Should return the original dict unchanged
    assert result == {"foo": "bar"}
    mock_logger.bind.assert_called_once_with(op=op)
    mock_logger.bind.return_value.error.assert_called_once()


def test_update_commit_event_with_uri_success():
    commit_event = {"foo": "bar"}
    uri = MagicMock()
    uri.collection = "app.bsky.feed.post"
    uri.http = "https://bsky.app/profile/user/post/123"
    uri.rkey = "rkey123"

    updated = _update_commit_event_with_uri(commit_event.copy(), uri)
    assert updated["type"] == "app.bsky.feed.post"
    assert updated["uri"] == "https://bsky.app/profile/user/post/123"
    assert updated["uri_rkey"] == "rkey123"
    assert updated["foo"] == "bar"


@patch("sinitaivas_live.parser.logger")
def test_update_commit_event_with_uri_exception(mock_logger):
    commit_event = {"foo": "bar"}
    uri = MagicMock()
    # Simulate exception when accessing uri.collection
    type(uri).collection = property(
        lambda self: (_ for _ in ()).throw(Exception("fail"))
    )
    type(uri).http = property(lambda self: "https://bsky.app/profile/user/post/123")
    type(uri).rkey = property(lambda self: "rkey123")

    result = _update_commit_event_with_uri(commit_event.copy(), uri)
    # Should return the original dict unchanged
    assert result == {"foo": "bar"}
    mock_logger.bind.assert_called_once_with(uri=uri)
    mock_logger.bind.return_value.error.assert_called_once()
