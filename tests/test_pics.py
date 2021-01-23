#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

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
    pic = next(pic for pic in conftest.pics if url.endswith(pic.path))
    assert pic.topic == topic


def test_year(conn: connection, dbx: conftest.MockDropbox) -> None:
    year = "2002"
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=[year])
    assert_valid_returns(url, timestamp, description)
    pic = next(pic for pic in conftest.pics if url.endswith(pic.path))
    assert pic.taken_at.year == int(year)


def test_user(conn: connection, dbx: conftest.MockDropbox) -> None:
    user = "slack_nick3"
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=[user])
    assert_valid_returns(url, timestamp, description)
    pic = next(pic for pic in conftest.pics if url.endswith(pic.path))
    assert 3 in pic.faces


def test_user_exclusive(conn: connection, dbx: conftest.MockDropbox) -> None:
    user = "slack_nick3"
    exclusive_pic = "test_pic7"
    # get seed that returns nonexclusive
    for seed in range(1, 10):
        with conn.cursor() as cursor:
            cursor.execute(f"select setseed(0.{seed})")
        url1, timestamp, description = pictures.get_pic(conn, dbx, arg_list=[user])
        assert_valid_returns(url1, timestamp, description)
        if not url1.endswith(exclusive_pic):
            break
    else:
        raise Exception("could not find good seed")

    with conn.cursor() as cursor:
        cursor.execute(f"select setseed(0.{seed})")
    url2, timestamp, description = pictures.get_pic(conn, dbx, arg_list=["kun", user])
    assert_valid_returns(url2, timestamp, description)
    assert url2.endswith(exclusive_pic)


def test_multiple_users(conn: connection, dbx: conftest.MockDropbox) -> None:
    users = ["slack_nick11", "slack_nick3"]
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=users)
    assert_valid_returns(url, timestamp, description)
    pic = next(pic for pic in conftest.pics if url.endswith(pic.path))
    assert {11, 3}.issubset(pic.faces), f"Wrong picture {pic}"


def test_multiple_users_exclusive(conn: connection, dbx: conftest.MockDropbox) -> None:
    users = ["slack_nick2", "slack_nick3"]
    exclusive_pic = "test_pic4"
    # get seed that returns nonexclusive
    for seed in range(0, 20):
        with conn.cursor() as cursor:
            cursor.execute(f"select setseed(0.{seed})")
        url1, timestamp, description = pictures.get_pic(conn, dbx, arg_list=users)
        assert_valid_returns(url1, timestamp, description)
        if not url1.endswith(exclusive_pic):
            break
    else:
        raise Exception("could not find good seed")

    with conn.cursor() as cursor:
        cursor.execute(f"select setseed(0.{seed})")
    url2, timestamp, description = pictures.get_pic(conn, dbx, arg_list=["kun"] + users)
    assert_valid_returns(url2, timestamp, description)
    assert url2.endswith(exclusive_pic)
    for _ in range(10):
        url3, timestamp, description = pictures.get_pic(
            conn, dbx, arg_list=["kun"] + users
        )
        assert_valid_returns(url3, timestamp, description)
        pic = next(pic for pic in conftest.pics if url3.endswith(pic.path))
        assert pic.faces == [2, 3], f"Wrong picture {pic}"


def test_multiple_args(conn: connection, dbx: conftest.MockDropbox) -> None:
    arg_list = ["slack_nick2", "topic1", "2001"]
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=arg_list)
    assert_valid_returns(url, timestamp, description)
    pic = next(pic for pic in conftest.pics if url.endswith(pic.path))
    assert pic.topic == "topic1"
    assert pic.taken_at.year == 2001
    assert 2 in pic.faces


def test_reduce_args(conn: connection, dbx: conftest.MockDropbox) -> None:
    arg_list = ["kun", "slack_nick11"]
    url, timestamp, description = pictures.get_pic(conn, dbx, arg_list=arg_list)
    assert description == (
        "Fant ikke bilde med `kun`, `slack_nick11`. "
        "Her er et bilde med `slack_nick11` i stedet."
    )


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
    pic = next(pic for pic in conftest.pics if url.endswith(pic.path))
    assert 5 in pic.faces


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
