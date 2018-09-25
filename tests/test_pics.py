#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.droppics import DropPics

from psycopg2.extensions import connection


def assert_valid_returns(url: str, timestamp: int, description: str) -> None:
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description == "" or description.startswith("Her er et bilde med")
    assert not description.startswith("Im so stoopid")


def test_random(db_connection: connection, drop_pics: DropPics) -> None:
    url, timestamp, description = drop_pics.get_pic(db=db_connection, arg_list=None)
    assert_valid_returns(url, timestamp, description)


def test_topic(db_connection: connection, drop_pics: DropPics) -> None:
    topic = "topic1"
    url, timestamp, description = drop_pics.get_pic(db_connection, arg_list=[topic])
    assert_valid_returns(url, timestamp, description)


def test_year(db_connection: connection, drop_pics: DropPics) -> None:
    year = "2002"
    url, timestamp, description = drop_pics.get_pic(db_connection, arg_list=[year])
    assert_valid_returns(url, timestamp, description)


def test_user(db_connection: connection, drop_pics: DropPics) -> None:
    user = "slack_nick3"
    url, timestamp, description = drop_pics.get_pic(db_connection, arg_list=[user])
    assert_valid_returns(url, timestamp, description)


def test_multiple_users(db_connection: connection, drop_pics: DropPics) -> None:
    users = ["slack_nick11", "slack_nick3"]
    url, timestamp, description = drop_pics.get_pic(db_connection, arg_list=users)
    assert_valid_returns(url, timestamp, description)


def test_multiple_args(db_connection: connection, drop_pics: DropPics) -> None:
    arg_list = ["slack_nick2", "topic1", "2001"]
    url, timestamp, description = drop_pics.get_pic(db_connection, arg_list=arg_list)
    assert_valid_returns(url, timestamp, description)


# Errors:
def test_error_txt(db_connection: connection, drop_pics: DropPics) -> None:
    url, timestamp, description = drop_pics.get_pic(db_connection, arg_list=["2000"])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Im so stoopid")
    assert description.endswith("Her er et tilfeldig bilde i stedet:")


def test_error_txt_with_valid(db_connection: connection, drop_pics: DropPics) -> None:
    url, timestamp, description = drop_pics.get_pic(
        db_connection, arg_list=["1999", "slack_nick5"]
    )
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Im so stoopid")
    assert "Her er et bilde med" in description


def test_error_txt_with_impossible_combination(
    db_connection: connection, drop_pics: DropPics
) -> None:
    url, timestamp, description = drop_pics.get_pic(
        db_connection, arg_list=["2001", "topic3"]
    )
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Fant ikke")
    assert "Her er et bilde med" in description
