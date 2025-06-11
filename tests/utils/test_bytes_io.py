from utils.bytes_io import convert_bytes_to_str


class DummyLogger:
    def __init__(self):
        self.called = False
        self.obj = None

    def bind(self, obj):
        self.obj = obj
        return self

    def warning(self, msg):
        self.called = True


def test_convert_bytes_to_str_bytes_base64(monkeypatch):
    # b'abc' -> base64 is 'YWJj'
    assert convert_bytes_to_str(b"abc") == "YWJj"


def test_convert_bytes_to_str_bytes_non_utf8(monkeypatch):
    # Patch logger to check warning
    import utils.bytes_io as bytes_io_mod

    dummy_logger = DummyLogger()
    monkeypatch.setattr(bytes_io_mod, "logger", dummy_logger)

    # bytes that can't be decoded as utf-8, but base64 always works, so force UnicodeDecodeError
    # by patching base64.b64encode to raise UnicodeDecodeError
    def fake_b64encode(obj):
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "reason")

    monkeypatch.setattr(bytes_io_mod.base64, "b64encode", fake_b64encode)
    result = convert_bytes_to_str(b"\xff\xfe")
    assert result == b"\xff\xfe".hex()
    assert dummy_logger.called


def test_convert_bytes_to_str_list():
    data = [b"foo", b"bar"]
    result = convert_bytes_to_str(data)
    assert result == ["Zm9v", "YmFy"]


def test_convert_bytes_to_str_dict():
    data = {b"key": b"value"}
    result = convert_bytes_to_str(data)
    assert result == {"a2V5": "dmFsdWU="}


def test_convert_bytes_to_str_nested():
    data = {
        b"k1": [b"v1", {b"k2": b"v2"}],
        "plain": 123,
    }
    result = convert_bytes_to_str(data)
    assert result == {
        "azE=": ["djE=", {"azI=": "djI="}],
        "plain": 123,
    }
