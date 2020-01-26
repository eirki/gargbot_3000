#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt

from psycopg2.extensions import connection

from gargbot_3000 import pictures
from tests import conftest


def assert_valid_returns(url: str, timestamp: dt.datetime, description: str) -> None:
    assert url.startswith("https")
    assert type(timestamp) == dt.datetime
    assert description == "" or description.startswith("Her er et bilde med")
    assert not description.startswith("Im so stoopid")


def test_random(conn: connection, dbx: conftest.MockDropbox) -> None:
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=None)
    assert_valid_returns(url, timestamp, description)


def test_topic(conn: connection, dbx: conftest.MockDropbox) -> None:
    topic = "topic1"
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=[topic])
    assert_valid_returns(url, timestamp, description)


def test_year(conn: connection, dbx: conftest.MockDropbox) -> None:
    year = "2002"
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=[year])
    assert_valid_returns(url, timestamp, description)


def test_user(conn: connection, dbx: conftest.MockDropbox) -> None:
    user = "slack_nick3"
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=[user])
    assert_valid_returns(url, timestamp, description)


def test_multiple_users(conn: connection, dbx: conftest.MockDropbox) -> None:
    users = ["slack_nick11", "slack_nick3"]
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=users)
    assert_valid_returns(url, timestamp, description)


def test_multiple_args(conn: connection, dbx: conftest.MockDropbox) -> None:
    arg_list = ["slack_nick2", "topic1", "2001"]
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=arg_list)
    assert_valid_returns(url, timestamp, description)


# Errors:
def test_error_txt(conn: connection, dbx: conftest.MockDropbox) -> None:
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=["2000"])
    assert url.startswith("https")
    assert type(timestamp) == dt.datetime
    assert description.startswith("Im so stoopid")
    assert description.endswith("Her er et tilfeldig bilde i stedet.")


def test_error_txt_with_valid(conn: connection, dbx: conftest.MockDropbox) -> None:
    url, timestamp, description = pictures.get_pic(
        conn, dbx, arg_list=["1999", "slack_nick5"]
    )
    assert url.startswith("https")
    assert type(timestamp) == dt.datetime
    assert description.startswith("Im so stoopid")
    assert "Her er et bilde med" in description


def test_error_txt_with_impossible_combination(
    conn: connection, dbx: conftest.MockDropbox
) -> None:
    url, timestamp, description = pictures.get_pic(
        conn, dbx, arg_list=["2001", "topic3"]
    )
    assert url.startswith("https")
    assert type(timestamp) == dt.datetime
    assert description.startswith("Fant ikke")
    assert "Her er et bilde med" in description
