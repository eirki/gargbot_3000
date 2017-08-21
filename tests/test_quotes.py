#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from context import config, quotes, database_manager


@pytest.fixture
def db_connection():
    db_connection = database_manager.connect_to_database()
    yield db_connection
    db_connection.close()


@pytest.fixture
def quotes_db(db_connection):
    return quotes.Quotes(db=db_connection)


@pytest.fixture
def slack_nick_to_db_id(quotes_db):
    return quotes_db.get_users()


def test_garg_vidoi(quotes_db):
    text = quotes_db.garg("vidoi")
    assert text.startswith("https://www.youtube.com/watch?v=")


def test_garg_random(quotes_db):
    text = quotes_db.garg("random")
    assert text.startswith("http") or "www" in text


def test_garg_quote_random(quotes_db):
    text = quotes_db.garg("quote")
    assert "------\n- " in text


def test_garg_quote_user(quotes_db, slack_nick_to_db_id):
    user = list(slack_nick_to_db_id.keys())[0]
    text = quotes_db.garg("quote", user)
    assert f"------\n- {user}" in text


def test_msn_random(quotes_db):
    date, conv = quotes_db.msn()
    assert type(date) == str
    assert type(conv) == list


def test_msn_user(quotes_db, slack_nick_to_db_id):
    user = list(slack_nick_to_db_id.keys())[0]
    date, conv = quotes_db.msn(user)
    assert type(date) == str
    assert type(conv) == list
    user_nicks = set(nick.lower() for nick in config.slack_to_msn_nicks[user])
    conv_nicks = set(nick.lower() for nick, msg, color in conv)
    assert user_nicks.intersection(conv_nicks)
