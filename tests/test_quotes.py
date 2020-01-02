#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt

from psycopg2.extensions import connection

from gargbot_3000 import config, quotes
from tests import conftest


def test_forum_random(db_connection: connection):
    text, user, avatar_url, date, url, desc = quotes.forum(db_connection, args=None)
    assert isinstance(date, dt.datetime)
    assert url.startswith(config.forum_url)
    assert "*" in text
    assert len(user) > 0
    assert desc == " "


def test_forum_user(db_connection: connection):
    in_user = conftest.users[0]
    text, out_user, avatar_url, date, url, desc = quotes.forum(
        db_connection, args=[in_user.slack_nick]
    )
    assert isinstance(date, dt.datetime)
    assert url.startswith(config.forum_url)
    assert "*" in text
    assert out_user == in_user.slack_nick
    assert avatar_url.endswith(f"{in_user.db_id}.jpg")
    assert desc == " "


def test_forum_user_nonexistent(db_connection: connection):
    text, out_user, avatar_url, date, url, desc = quotes.forum(
        db_connection, args=["Non-existant user"]
    )
    assert desc == (
        "Gargling not found: Non-existant user. Husk å bruke slack nick. "
        "Her er et tilfeldig quote i stedet."
    )


def test_msn_random(db_connection: connection):
    date, conv, desc = quotes.msn(db_connection, args=None)
    assert type(date) == str
    assert type(conv) == list
    assert desc is None


def test_msn_user(db_connection: connection):
    user = conftest.users[0]
    date, conv, desc = quotes.msn(db_connection, args=[user.slack_nick])
    assert type(date) == str
    assert type(conv) == list
    assert desc is None


def test_msn_user_nonexistent(db_connection: connection):
    date, conv, desc = quotes.msn(db_connection, args=["Non-existant user"])
    assert desc == (
        "Gargling not found: Non-existant user. Husk å bruke slack nick. "
        "Her er en tilfeldig samtale i stedet."
    )
