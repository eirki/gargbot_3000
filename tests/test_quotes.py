#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt

from psycopg2.extensions import connection

from gargbot_3000 import config, quotes
from tests import conftest


def test_forum_random(conn: connection):
    text, user, avatar_url, date, url, desc = quotes.forum(conn, args=None)
    assert isinstance(date, dt.datetime)
    assert url.startswith(config.forum_url)
    assert "*" in text
    assert len(user) > 0
    assert desc == " "


def test_forum_user(conn: connection):
    in_user = conftest.users[0]
    text, out_user, avatar_url, date, url, desc = quotes.forum(
        conn, args=[in_user.slack_nick]
    )
    assert isinstance(date, dt.datetime)
    assert url.startswith(config.forum_url)
    assert "*" in text
    assert out_user == in_user.slack_nick
    assert avatar_url.endswith(f"{in_user.db_id}.jpg")
    assert desc == " "


def test_forum_user_nonexistent(conn: connection):
    text, out_user, avatar_url, date, url, desc = quotes.forum(
        conn, args=["Non-existant user"]
    )
    assert desc == (
        "Gargling not found: Non-existant user. Husk å bruke slack nick. "
        "Her er et tilfeldig quote i stedet."
    )


def test_msn_random(conn: connection):
    date, conv, desc = quotes.msn(conn, args=None)
    assert type(date) == str
    assert type(conv) == list
    assert desc is None


def test_msn_user(conn: connection):
    user = conftest.users[0]
    date, conv, desc = quotes.msn(conn, args=[user.slack_nick])
    assert type(date) == str
    assert type(conv) == list
    assert desc is None


def test_msn_user_nonexistent(conn: connection):
    date, conv, desc = quotes.msn(conn, args=["Non-existant user"])
    assert desc == (
        "Gargling not found: Non-existant user. Husk å bruke slack nick. "
        "Her er en tilfeldig samtale i stedet."
    )
