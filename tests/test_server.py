#! /usr/bin/env python3
# coding: utf-8
import json
import typing as t
from types import SimpleNamespace

import pytest
from flask import testing
from psycopg2.extensions import connection

from gargbot_3000 import config, database_manager, server


@pytest.fixture
def client(db_connection) -> t.Generator[testing.FlaskClient, None, None]:
    server.app.pool = MockPool(db_connection)
    yield server.app.test_client()


class MockPool(database_manager.ConnectionPool):
    def __init__(self, db_connection: connection) -> None:
        self.db_connection = db_connection

    def getconn(self) -> connection:
        return self.db_connection

    def putconn(self, conn: connection):
        pass

    def closeall(self):
        pass


class MockRequests:
    def post(self, url, json):
        self.url = url
        self.json = json
        mock_response = SimpleNamespace(text="text")
        return mock_response


class MockCommands:
    def execute(self, command_str, args, db_connection, drop_pics, quotes_db):
        self.command_str = command_str
        self.args = args
        self.db_connection = db_connection
        self.drop_pics = drop_pics
        self.quotes_db = quotes_db
        return {"text": "text"}


def test_home(client: testing.FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.data == b"home"


def test_slash_cmd_ping(client: testing.FlaskClient):
    params = {
        "token": config.slack_verification_token,
        "command": "/ping",
        "text": "",
        "trigger_id": "test_slash_cmd_ping",
    }
    response = client.post("/slash", data=params)
    assert response.status_code == 200
    assert json.loads(response.data.decode()) == {
        "text": "GargBot 3000 is active. Beep boop beep",
        "response_type": "in_channel",
    }


def test_slash_cmd_gargbot(client: testing.FlaskClient):
    params = {
        "token": config.slack_verification_token,
        "command": "/gargbot",
        "text": "",
        "trigger_id": "test_slash_cmd_gargbot",
    }
    response = client.post("/slash", data=params)
    assert response.status_code == 200
    data = json.loads(response.data.decode())
    assert data["text"].startswith("Beep boop beep!")
    assert "/pic" in data["text"]


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", ["", "arg1", "arg1 arg2"])
def test_slash(
    client: testing.FlaskClient, db_connection: connection, monkeypatch, cmd, args
):
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)

    params = {
        "token": config.slack_verification_token,
        "command": "/" + cmd,
        "text": args,
        "trigger_id": "test_slash_" + cmd,
    }
    response = client.post("/slash", data=params)
    assert response.status_code == 200
    assert mock_commands.command_str == cmd
    assert mock_commands.args == args.split()
    assert mock_commands.db_connection == db_connection


def test_interactive_share(client: testing.FlaskClient, monkeypatch):
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)
    action = "share"
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [
                    {
                        "name": action,
                        "value": json.dumps(
                            {"original_response": {"text": "original_text"}}
                        ),
                    }
                ],
                "response_url": "response_url",
            }
        )
    }
    response = client.post("/interactive", data=params)
    assert response.status_code == 200

    data = json.loads(response.data.decode())
    assert data["replace_original"] is False
    assert data["response_type"] == "in_channel"
    assert data["text"] == "original_text"

    assert mock_requests.url == "response_url"
    assert mock_requests.json["replace_original"] is True
    assert mock_requests.json["response_type"] == "ephemeral"
    assert mock_requests.json["text"] == "Sharing is caring!"


def test_interactive_cancel(client: testing.FlaskClient):
    action = "cancel"
    params = {
        "payload": json.dumps(
            {"token": config.slack_verification_token, "actions": [{"name": action}]}
        )
    }
    response = client.post("/interactive", data=params)
    assert response.status_code == 200
    data = json.loads(response.data.decode())
    assert data["replace_original"] is True
    assert data["response_type"] == "ephemeral"
    assert data["text"].startswith("Canceled!")


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
def test_interactive_shuffle(
    client: testing.FlaskClient, db_connection: connection, monkeypatch, cmd, args
):
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)

    action = "shuffle"
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [
                    {
                        "name": action,
                        "value": json.dumps(
                            {"original_func": cmd, "original_args": args}
                        ),
                    }
                ],
                "callback_id": "callback_id",
            }
        )
    }
    response = client.post("/interactive", data=params)
    assert response.status_code == 200

    data = json.loads(response.data.decode())
    assert data["replace_original"] is True
    assert data["response_type"] == "ephemeral"
    assert data["text"] == "text"

    assert mock_commands.command_str == cmd
    assert mock_commands.args == args
    assert mock_commands.db_connection == db_connection


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
def test_interactive_gargbot_commands(
    client: testing.FlaskClient, db_connection: connection, monkeypatch, cmd
):
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [{"name": cmd}],
                "trigger_id": "trigger_id",
            }
        )
    }
    response = client.post("/interactive", data=params)
    assert response.status_code == 200
    data = json.loads(response.data.decode())
    print(data)
    assert "attachments" in data
