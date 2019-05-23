#! /usr/bin/env python3
# coding: utf-8
import json
import typing as t
from types import SimpleNamespace

import pytest
from flask import testing
from psycopg2.extensions import connection

from gargbot_3000 import config, database_manager, server
from tests import conftest


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
    def __init__(self):
        self.url = None
        self.urls = []
        self.json = None
        self.jsons = []

    def post(self, url: str, json: dict):
        self.url = url
        self.urls.append(url)
        self.json = json
        self.jsons.append(json)
        mock_response = SimpleNamespace(text="text")
        return mock_response


class MockCommands:
    def execute(self, command_str, args, db_connection, drop_pics, quotes_db):
        self.command_str = command_str
        self.args = args
        self.db_connection = db_connection
        self.drop_pics = drop_pics
        self.quotes_db = quotes_db
        if command_str == "msn":
            return {"text": command_str, "attachments": [{"blocks": []}]}
        else:
            return {"text": command_str, "blocks": []}


def test_home(client: testing.FlaskClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.data == b"home"


def test_slash_cmd_ping(client: testing.FlaskClient, monkeypatch):
    params = {
        "token": config.slack_verification_token,
        "command": "/ping",
        "text": "",
        "trigger_id": "test_slash_cmd_ping",
        "response_url": "response_url",
    }
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)

    response = client.post("/slash", data=params)
    assert response.status_code == 200
    assert mock_requests.url == "response_url"
    assert mock_requests.json["text"] == "GargBot 3000 is active. Beep boop beep"
    assert mock_requests.json["response_type"] == "in_channel"


def test_slash_cmd_gargbot(client: testing.FlaskClient, monkeypatch):
    params = {
        "token": config.slack_verification_token,
        "command": "/gargbot",
        "text": "",
        "trigger_id": "test_slash_cmd_gargbot",
        "response_url": "response_url",
    }
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)

    response = client.post("/slash", data=params)
    assert response.status_code == 200
    assert mock_requests.url == "response_url"
    assert mock_requests.json["text"].startswith("Beep boop beep!")
    assert "/pic" in mock_requests.json["text"]


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", ["", "arg1", "arg1 arg2"])
def test_slash(
    client: testing.FlaskClient, db_connection: connection, monkeypatch, cmd, args
):
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)

    params = {
        "token": config.slack_verification_token,
        "command": "/" + cmd,
        "text": args,
        "trigger_id": "test_slash_" + cmd,
        "response_url": "response_url",
    }
    response = client.post("/slash", data=params)
    assert response.status_code == 200
    assert mock_commands.command_str == cmd
    assert mock_commands.args == args.split()
    assert mock_commands.db_connection == db_connection

    assert mock_requests.url == "response_url"
    assert mock_requests.json["text"] == cmd
    action_ids = {
        elem["action_id"] for elem in mock_requests.json["blocks"][-1]["elements"]
    }
    assert all(action_id in action_ids for action_id in ["share", "shuffle", "cancel"])


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
def test_interactive_share(
    client: testing.FlaskClient, monkeypatch, cmd: str, args: t.List[str]
):
    user = conftest.users[0]
    action = "share"
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [
                    {
                        "action_id": action,
                        "block_id": "share_buttons",
                        "value": json.dumps(
                            {
                                "original_response": {
                                    "text": "original_text",
                                    "blocks": [],
                                },
                                "original_func": cmd,
                                "original_args": args,
                            }
                        ),
                    }
                ],
                "response_url": "response_url",
                "user": {"id": user.slack_id, "name": user.slack_nick},
            }
        )
    }
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)
    response = client.post("/interactive", data=params)
    assert response.status_code == 200

    assert mock_requests.urls[0] == "response_url"
    assert mock_requests.jsons[0]["replace_original"] is True
    assert mock_requests.jsons[0]["response_type"] == "ephemeral"
    assert mock_requests.jsons[0]["text"] == "Sharing is caring!"

    assert mock_requests.urls[1] == "response_url"
    assert mock_requests.jsons[1]["replace_original"] is False
    assert mock_requests.jsons[1]["response_type"] == "in_channel"
    assert mock_requests.jsons[1]["text"] == "original_text"


def test_interactive_cancel(client: testing.FlaskClient, monkeypatch):
    action = "cancel"
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [{"action_id": action, "block_id": "share_buttons"}],
                "response_url": "response_url",
            }
        )
    }
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)
    response = client.post("/interactive", data=params)
    assert response.status_code == 200
    assert mock_requests.url == "response_url"
    assert mock_requests.json["replace_original"] is True
    assert mock_requests.json["response_type"] == "ephemeral"
    assert mock_requests.json["text"].startswith("Canceled!")


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
def test_interactive_shuffle(
    client: testing.FlaskClient, db_connection: connection, monkeypatch, cmd, args
):
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)

    action = "shuffle"
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [
                    {
                        "action_id": action,
                        "block_id": "share_buttons",
                        "value": json.dumps(
                            {"original_func": cmd, "original_args": args}
                        ),
                    }
                ],
                "response_url": "response_url",
            }
        )
    }
    response = client.post("/interactive", data=params)
    assert response.status_code == 200
    assert mock_requests.url == "response_url"
    assert mock_requests.json["replace_original"] is True
    assert mock_requests.json["response_type"] == "ephemeral"
    assert mock_requests.json["text"] == cmd

    assert mock_commands.command_str == cmd
    assert mock_commands.args == args
    assert mock_commands.db_connection == db_connection


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
def test_interactive_gargbot_commands(
    client: testing.FlaskClient, db_connection: connection, monkeypatch, cmd
):
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)
    mock_requests = MockRequests()
    monkeypatch.setattr("gargbot_3000.server.requests", mock_requests)
    params = {
        "payload": json.dumps(
            {
                "token": config.slack_verification_token,
                "actions": [{"action_id": cmd, "block_id": "commands_buttons"}],
                "response_url": "response_url",
            }
        )
    }
    response = client.post("/interactive", data=params)
    assert response.status_code == 200

    assert mock_commands.command_str == cmd
    assert mock_commands.db_connection == db_connection

    assert mock_requests.url == "response_url"
    assert mock_requests.url == "response_url"
    assert mock_requests.json["text"] == cmd
    action_ids = {
        elem["action_id"] for elem in mock_requests.json["blocks"][-1]["elements"]
    }
    assert all(action_id in action_ids for action_id in ["share", "shuffle", "cancel"])
