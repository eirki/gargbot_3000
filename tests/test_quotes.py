#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from gargbot_3000 import quotes
from gargbot_3000 import config
from tests import conftest

import datetime as dt

# Typing
from psycopg2.extensions import connection


@pytest.fixture
def quotes_db(db_connection: connection):
    return quotes.Quotes(db=db_connection)


def test_garg_quote_random(db_connection: connection, quotes_db: quotes.Quotes):
    text, user, avatar_url, post_timestamp, url = quotes_db.forum(
        db_connection, args=None
    )
    assert isinstance(post_timestamp, dt.datetime)
    assert url.startswith(config.forum_url)
    assert len(text) > 0
    assert len(user) > 0


def test_garg_quote_user(db_connection: connection, quotes_db: quotes.Quotes):
    in_user = conftest.users[0]
    text, out_user, avatar_url, post_timestamp, url = quotes_db.forum(
        db_connection, args=[in_user.slack_nick]
    )
    assert isinstance(post_timestamp, dt.datetime)
    assert url.startswith(config.forum_url)
    assert len(text) > 0
    assert out_user == in_user.slack_nick
    assert avatar_url.endswith(f"{in_user.db_id}.jpg")


def test_msn_random(db_connection: connection, quotes_db: quotes.Quotes):
    date, conv = quotes_db.msn(db_connection, args=None)
    assert type(date) == str
    assert type(conv) == list


def test_msn_user(db_connection: connection, quotes_db: quotes.Quotes):
    user = conftest.users[0]
    date, conv = quotes_db.msn(db_connection, args=[user.slack_nick])
    assert type(date) == str
    assert type(conv) == list
