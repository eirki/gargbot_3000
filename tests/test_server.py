#! /usr/bin/env python3
# coding: utf-8
import json
from types import SimpleNamespace

import pytest
import flask

from gargbot_3000 import server
from gargbot_3000 import config
from tests import conftest

from psycopg2.extensions import connection


test_client: flask.testing.FlaskClient = server.app.test_client()


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


def test_home(db_connection: connection):
    response = test_client.get("/")
    assert response.status_code == 200
    assert response.data == b"home"


def test_slash_cmd_ping(db_connection: connection):
    params = {
        "token": config.slack_verification_token,
        "command": "/ping",
        "text": "",
        "trigger_id": "test_slash_cmd_ping",
    }
    response = test_client.post("/slash", data=params)
    assert response.status_code == 200
    assert json.loads(response.data.decode()) == {
        "text": "GargBot 3000 is active. Beep boop beep",
        "response_type": "in_channel",
    }


@pytest.mark.parametrize("cmd", ["pic", "quote", "msn"])
@pytest.mark.parametrize("args", ["", "arg1", "arg1 arg2"])
def test_slash(db_connection: connection, monkeypatch, cmd, args):
    def return_db():
        return db_connection

    monkeypatch.setattr("gargbot_3000.server.get_db", return_db)

    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)

    monkeypatch.setattr("gargbot_3000.server.get_pics", conftest.get_pics(db_connection))

    params = {
        "token": config.slack_verification_token,
        "command": "/" + cmd,
        "text": args,
        "trigger_id": "test_slash_" + cmd,
    }
    response = test_client.post("/slash", data=params)
    assert response.status_code == 200
    assert mock_commands.command_str == cmd
    assert mock_commands.args == args.split()
    assert mock_commands.db_connection == db_connection


def test_interactive_share(monkeypatch):
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
    response = test_client.post("/interactive", data=params)
    assert response.status_code == 200

    data = json.loads(response.data.decode())
    assert data["replace_original"] is False
    assert data["response_type"] == "in_channel"
    assert data["text"] == "original_text"

    assert mock_requests.url == "response_url"
    assert mock_requests.json["replace_original"] is True
    assert mock_requests.json["response_type"] == "ephemeral"
    assert mock_requests.json["text"] == "Sharing is caring!"


def test_interactive_cancel():
    action = "cancel"
    params = {
        "payload": json.dumps(
            {"token": config.slack_verification_token, "actions": [{"name": action}]}
        )
    }
    response = test_client.post("/interactive", data=params)
    assert response.status_code == 200
    data = json.loads(response.data.decode())
    assert data["replace_original"] is True
    assert data["response_type"] == "ephemeral"
    assert data["text"].startswith("Canceled!")


@pytest.mark.parametrize("cmd", ["pic", "quote", "msn"])
@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
def test_interactive_shuffle(
    db_connection: connection, monkeypatch, cmd, args
):
    def return_db():
        return db_connection

    monkeypatch.setattr("gargbot_3000.server.get_db", return_db)
    mock_commands = MockCommands()
    monkeypatch.setattr("gargbot_3000.server.commands", mock_commands)

    monkeypatch.setattr("gargbot_3000.server.get_pics", conftest.drop_pics)

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
    response = test_client.post("/interactive", data=params)
    assert response.status_code == 200

    data = json.loads(response.data.decode())
    assert data["replace_original"] is True
    assert data["response_type"] == "ephemeral"
    assert data["text"] == "text"

    assert mock_commands.command_str == cmd
    assert mock_commands.args == args
    assert mock_commands.db_connection == db_connection
