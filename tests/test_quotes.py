#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from context import config, quotes, database_manager


@pytest.fixture
def db_connection():
    db_connection = database_manager.connect_to_database()
    try:
        yield db_connection
    finally:
        db_connection.close()


@pytest.fixture
def quotes_db(db_connection):
    return quotes.Quotes(db=db_connection)


@pytest.fixture
def slack_nick_to_db_id(db_connection, quotes_db):
    with db_connection as cursor:
        response = quotes_db._get_users(cursor)
    return response


def test_garg_vidoi(db_connection, quotes_db):
    text = quotes_db.garg(db_connection, "vidoi")
    assert text.startswith("https://www.youtube.com/watch?v=")


def test_garg_random(db_connection, quotes_db):
    text = quotes_db.garg(db_connection, "random")
    assert text.startswith("http") or "www" in text


def test_garg_quote_random(db_connection, quotes_db):
    text = quotes_db.garg(db_connection, "quote")
    assert "------\n- " in text


def test_garg_quote_user(quotes_db, db_connection, slack_nick_to_db_id):
    user = list(slack_nick_to_db_id.keys())[0]
    text = quotes_db.garg(db_connection, "quote", user)
    assert f"------\n- {user}" in text


def test_msn_random(db_connection, quotes_db):
    date, conv = quotes_db.msn(db_connection)
    assert type(date) == str
    assert type(conv) == list


def test_msn_user(quotes_db, db_connection, slack_nick_to_db_id):
    user = list(slack_nick_to_db_id.keys())[0]
    date, conv = quotes_db.msn(db_connection, user)
    assert type(date) == str
    assert type(conv) == list
    user_nicks = set(nick.lower() for nick in config.slack_to_msn_nicks[user])
    conv_nicks = set(nick.lower() for nick, msg, color in conv)
    assert user_nicks.intersection(conv_nicks)
