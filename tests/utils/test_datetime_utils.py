import pytest
from datetime import datetime, timezone

import utils.datetime_utils as datetime_utils
import utils.datetime_fmt as dt_fmt


def test_current_datetime_utc_is_utc():
    dt = datetime_utils.current_datetime_utc()
    assert dt.tzinfo == timezone.utc


def test_datetime_as_zulu_str():
    dt = datetime(2024, 6, 1, 12, 34, 56, 789000, tzinfo=timezone.utc)
    zulu_str = datetime_utils.datetime_as_zulu_str(dt)
    assert zulu_str == dt.strftime(dt_fmt.DATETIME_ZULU_FORMAT)
    assert zulu_str.endswith("Z")


def test_datetime_as_date_and_hour_str():
    dt = datetime(2024, 6, 1, 15, 0, 0, tzinfo=timezone.utc)
    date_hour_str = datetime_utils.datetime_as_date_and_hour_str(dt)
    assert date_hour_str == dt.strftime(dt_fmt.DATE_AND_HOUR_FORMAT)
    assert date_hour_str.endswith("T15")


def test_datetime_as_date_str():
    dt = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    date_str = datetime_utils.datetime_as_date_str(dt)
    assert date_str == dt.strftime(dt_fmt.DATE_FORMAT)
    assert date_str == "2024-06-01"


def test_str_to_date():
    date_str = "2024-06-01"
    dt = datetime_utils.str_to_date(date_str)
    assert dt == datetime.strptime(date_str, dt_fmt.DATE_FORMAT)
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 1


def test_str_to_zulu_datetime():
    zulu_str = "2024-06-01T12:34:56.789000Z"
    dt = datetime_utils.str_to_zulu_datetime(zulu_str)
    expected = datetime.strptime(zulu_str, dt_fmt.DATETIME_ZULU_FORMAT)
    assert dt == expected
    assert dt.year == 2024
    assert dt.month == 6
    assert dt.day == 1
    assert dt.hour == 12
    assert dt.minute == 34
    assert dt.second == 56
    assert dt.microsecond == 789000


@pytest.mark.parametrize("date_str", ["2020-02-29", "1999-12-31", "2024-01-01"])
def test_str_to_date_various(date_str):
    dt = datetime_utils.str_to_date(date_str)
    assert dt.strftime(dt_fmt.DATE_FORMAT) == date_str


@pytest.mark.parametrize(
    "zulu_str", ["2024-06-01T00:00:00.000000Z", "2023-01-15T23:59:59.123456Z"]
)
def test_str_to_zulu_datetime_various(zulu_str):
    dt = datetime_utils.str_to_zulu_datetime(zulu_str)
    assert dt.strftime(dt_fmt.DATETIME_ZULU_FORMAT) == zulu_str


def test_datetime_as_zulu_str_microseconds():
    dt = datetime(2024, 6, 1, 12, 34, 56, 1, tzinfo=timezone.utc)
    zulu_str = datetime_utils.datetime_as_zulu_str(dt)
    assert zulu_str.endswith("Z")
    assert "." in zulu_str
