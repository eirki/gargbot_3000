#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import datetime as dt

from psycopg2.extensions import connection

from gargbot_3000 import commands
from tests import conftest


def test_cmd_ping():
    response = commands.cmd_ping()
    assert response == {"text": "GargBot 3000 is active. Beep boop beep"}


def test_cmd_welcome():
    response = commands.cmd_welcome()
    assert response["text"].endswith(commands.command_explanation())


def test_cmd_hvem(conn: connection):
    arg_list = ["is", "it?"]
    response = commands.cmd_hvem(arg_list, conn)
    text = response["text"]
    assert any(text.startswith(user.first_name) for user in conftest.users)
    assert text.endswith("!")


def test_cmd_not_found():
    response = commands.execute(command_str="blarg", args=[], conn=None, dbx=None)
    assert response["text"].startswith("Beep boop beep!")
    assert "blarg" in response["text"]


def test_cmd_panic(monkeypatch):
    def blowup():
        1 / 0

    monkeypatch.setattr("gargbot_3000.commands.cmd_ping", blowup)
    response = commands.execute(command_str="ping", args=[], conn=None, dbx=None)
    assert response["text"].startswith("Error, error!")
    assert "division by zero" in response["text"]


def test_prettify_date():
    date = dt.datetime(2020, 1, 2, 0, 0, 0)
    pretty = commands.prettify_date(date)
    assert (
        pretty
        == "<!date^1577919600^{date_pretty} at 00:00| Thursday 02. January 2020 00:00>"
    )
