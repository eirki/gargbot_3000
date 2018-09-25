#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from gargbot_3000 import commands
from tests import conftest

# Typing
from psycopg2.extensions import connection


def test_cmd_ping():
    response = commands.cmd_ping()
    assert response == {"text": "GargBot 3000 is active. Beep boop beep"}


def test_cmd_welcome():
    response = commands.cmd_welcome()
    assert response["text"].endswith(commands.command_explanation)


def test_cmd_hvem(db_connection: connection):
    arg_list = ["is", "it?"]
    response = commands.cmd_hvem(arg_list, db_connection)
    text = response["text"]
    assert any(text.startswith(user.name) for user in conftest.users)
    assert text.endswith("!")


def test_cmd_not_found():
    response = commands.execute(
        command_str="blarg", args=[], db_connection=None, drop_pics=None, quotes_db=None
    )
    assert response["text"].startswith("Beep boop beep!")
    assert "blarg" in response["text"]


def test_cmd_panic(monkeypatch):
    def blowup():
        1 / 0

    monkeypatch.setattr("gargbot_3000.commands.cmd_ping", blowup)
    response = commands.execute(
        command_str="ping", args=[], db_connection=None, drop_pics=None, quotes_db=None
    )
    assert response["text"].startswith("Error, error!")
    assert "division by zero" in response["text"]
