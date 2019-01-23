#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from gargbot_3000 import quotes
from tests import conftest

# Typing
from psycopg2.extensions import connection


@pytest.fixture
def quotes_db(db_connection: connection):
    return quotes.Quotes(db=db_connection)


def test_garg_quote_random(db_connection: connection, quotes_db: quotes.Quotes):
    text = quotes_db.forum(db_connection, args=None)
    assert "------\n- " in text


def test_garg_quote_user(db_connection: connection, quotes_db: quotes.Quotes):
    user = conftest.users[0]
    text = quotes_db.forum(db_connection, args=[user.slack_nick])
    assert f"------\n- {user.slack_nick}" in text


def test_msn_random(db_connection: connection, quotes_db: quotes.Quotes):
    date, conv = quotes_db.msn(db_connection, args=None)
    assert type(date) == str
    assert type(conv) == list


def test_msn_user(db_connection: connection, quotes_db: quotes.Quotes):
    user = conftest.users[0]
    date, conv = quotes_db.msn(db_connection, args=[user.slack_nick])
    assert type(date) == str
    assert type(conv) == list
