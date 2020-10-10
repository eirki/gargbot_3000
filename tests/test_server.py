#! /usr/bin/env python3
# coding: utf-8
import json
from types import SimpleNamespace
import typing as t
from unittest.mock import patch

from flask import testing
from psycopg2.extensions import connection
import pytest

from gargbot_3000 import config
from tests import conftest


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
        mock_response = SimpleNamespace(text="text", raise_for_status=lambda: None)
        return mock_response


class MockCommands:
    def execute(self, command_str, args, conn, dbx) -> t.Dict[str, t.Any]:
        self.command_str = command_str
        self.args = args
        self.conn = conn
        self.dbx = dbx
        response = (
            {"text": command_str, "blocks": []}
            if command_str != "msn"
            else {"text": command_str, "attachments": [{"blocks": []}]}
        )
        return response


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
    assert (
        mock_requests.json["text"] == "GargBot 3000 is active. Beep boop beep"  # type: ignore
    )
    assert mock_requests.json["response_type"] == "in_channel"  # type: ignore


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
    assert mock_requests.json["text"].startswith("Beep boop beep!")  # type: ignore
    assert "/pic" in mock_requests.json["text"]  # type: ignore


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", ["", "arg1", "arg1 arg2"])
def test_slash(client: testing.FlaskClient, conn: connection, monkeypatch, cmd, args):
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
    assert mock_commands.conn == conn

    assert mock_requests.url == "response_url"
    assert mock_requests.json["text"] == cmd  # type: ignore
    action_ids = {
        elem["action_id"]
        for elem in mock_requests.json["blocks"][-1]["elements"]  # type: ignore
    }
    assert all(action_id in action_ids for action_id in ["share", "shuffle", "cancel"])


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
def test_interactive_share(
    client: testing.FlaskClient, monkeypatch, cmd: str, args: t.List[str]
):
    user = conftest.users[0]
    original_response: t.Dict[str, t.Any] = (
        {"text": cmd, "blocks": []}
        if cmd != "msn"
        else {"text": cmd, "attachments": [{"blocks": []}]}
    )
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
                                "original_response": original_response,
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
    assert mock_requests.jsons[0]["replace_original"] is True  # type: ignore
    assert mock_requests.jsons[0]["response_type"] == "ephemeral"  # type: ignore
    assert mock_requests.jsons[0]["text"] == "Sharing is caring!"  # type: ignore

    assert mock_requests.urls[1] == "response_url"
    assert mock_requests.jsons[1]["replace_original"] is False  # type: ignore
    assert mock_requests.jsons[1]["response_type"] == "in_channel"  # type: ignore
    assert mock_requests.jsons[1]["text"] == cmd  # type: ignore


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
    assert mock_requests.json["replace_original"] is True  # type: ignore
    assert mock_requests.json["response_type"] == "ephemeral"  # type: ignore
    assert mock_requests.json["text"].startswith("Canceled!")  # type: ignore


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
def test_interactive_shuffle(
    client: testing.FlaskClient, conn: connection, monkeypatch, cmd, args
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
    assert mock_requests.json["replace_original"] is True  # type: ignore
    assert mock_requests.json["response_type"] == "ephemeral"  # type: ignore
    assert mock_requests.json["text"] == cmd  # type: ignore

    assert mock_commands.command_str == cmd
    assert mock_commands.args == args
    assert mock_commands.conn == conn


@pytest.mark.parametrize("cmd", ["pic", "forum", "msn"])
def test_interactive_gargbot_commands(
    client: testing.FlaskClient, conn: connection, monkeypatch, cmd
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
    assert mock_commands.conn == conn

    assert mock_requests.url == "response_url"
    assert mock_requests.url == "response_url"
    assert mock_requests.json["text"] == cmd  # type: ignore
    action_ids = {
        elem["action_id"]
        for elem in mock_requests.json["blocks"][-1]["elements"]  # type: ignore
    }
    assert all(action_id in action_ids for action_id in ["share", "shuffle", "cancel"])


@patch("gargbot_3000.server.WebClient")
def test_auth(mock_SlackClient, client: testing.FlaskClient):
    user = conftest.users[0]
    mock_SlackClient.return_value.oauth_v2_access.return_value.data = {
        "ok": True,
        "team_id": config.slack_team_id,
        "user_id": user.slack_id,
    }
    response = client.get("/auth", query_string={"code": "code123"})
    assert response.status_code == 200
    assert "access_token" in response.json
    access_token = response.json["access_token"]
    response2 = client.get(
        "/is_authed", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response2.status_code == 200


@patch("gargbot_3000.server.WebClient")
def test_auth_wrong_team(mock_SlackClient, client: testing.FlaskClient):
    mock_SlackClient.return_value.oauth_v2_access.return_value.data = {
        "ok": True,
        "team_id": "wrong team_id",
        "user_id": "user.id",
    }
    response = client.get("/auth", query_string={"code": "code123"})
    assert response.status_code == 403


@patch("gargbot_3000.server.WebClient")
def test_auth_error(mock_SlackClient, client: testing.FlaskClient):
    mock_SlackClient.return_value.oauth_v2_access.return_value.data = {
        "ok": False,
        "error": "Something went wrong",
        "team_id": "wrong team_id",
        "user_id": "user.id",
    }
    response = client.get("/auth", query_string={"code": "code123"})
    assert response.status_code == 403


def test_not_authed(client: testing.FlaskClient):
    response = client.get("/is_authed")
    assert response.status_code == 401


def test_wrong_token(client: testing.FlaskClient):
    access_token = 12321
    response = client.get(
        "/is_authed", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("args", [[], ["arg1"], ["arg1", "arg2"]])
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_pic_api(mock_jwt, client: testing.FlaskClient, args: list, monkeypatch, dbx):
    monkeypatch.setattr("gargbot_3000.server.app.dbx", dbx)
    args_fmt = ",".join(args)
    url = f"/pic/{args_fmt}" if args else "/pic"
    response = client.get(url)
    assert response.status_code == 200
    assert response.json["url"].startswith("https://")
