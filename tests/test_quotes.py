#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from context import config, quotes, database_manager


@pytest.fixture
def quotes_db():
    db_connection = database_manager.connect_to_database()
    inited_quotes_db = quotes.Quotes(db=db_connection)
    yield inited_quotes_db
    db_connection.close()


def test_garg_vidoi(quotes_db):
    text = quotes_db.garg("vidoi")
    assert text.startswith("https://www.youtube.com/watch?v=")


def test_garg_random(quotes_db):
    text = quotes_db.garg("random")
    assert text.startswith("http") or "www" in text


def test_garg_quote_random(quotes_db):
    text = quotes_db.garg("quote")
    assert "------\n- " in text


def test_garg_quote_user(quotes_db):
    user = list(config.slack_id_to_nick.values())[0]
    text = quotes_db.garg("quote", user)
    assert f"------\n- {user}" in text


def test_msn_random(quotes_db):
    date, conv = quotes_db.msn()
    assert type(date) == str
    assert type(conv) == list


def test_msn_user(quotes_db):
    user = list(config.slack_id_to_nick.values())[0]
    date, conv = quotes_db.msn(user)
    assert type(date) == str
    assert type(conv) == list
    user_nicks = set(nick.lower() for nick in config.slack_to_msn_nicks[user])
    conv_nicks = set(nick.lower() for nick, msg, color in conv)
    assert user_nicks.intersection(conv_nicks)
