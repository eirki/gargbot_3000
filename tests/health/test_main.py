#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from dataclasses import dataclass
import typing as t
from unittest.mock import patch

from flask import testing
import pendulum
from psycopg2.extensions import connection
import pytest

from gargbot_3000 import config, health
from gargbot_3000.health import fitbit_, googlefit, polar, withings
from tests import conftest
from tests.health import test_fitbit, test_googlefit, test_polar, test_withings

modules = {
    "fitbit": (fitbit_, test_fitbit),
    "googlefit": (googlefit, test_googlefit),
    "polar": (polar, test_polar),
    "withings": (withings, test_withings),
}
services = ("service_name", ["withings", "fitbit", "googlefit", "polar"])


@pytest.mark.parametrize(*services)
@pytest.mark.parametrize("enable", [True, False])
@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_toggle_steps(
    mock_jwt_required,
    mock_jwt_identity,
    service_name: str,
    enable: bool,
    client: testing.FlaskClient,
    conn: connection,
):
    user = conftest.users[0]
    module, test_module = modules[service_name]
    test_module.register_user(user, conn, enable_steps=not enable)
    data = health.queries.health_status(conn, gargling_id=user.id)
    as_dict = {row["service"]: dict(row) for row in data}
    assert as_dict[service_name]["enable_steps"] is not enable

    mock_jwt_identity.return_value = user.id
    response = client.post(
        "/health_toggle",
        json={"measure": "steps", "service": service_name, "enable": enable},
    )
    assert response.status_code == 200

    data = health.queries.health_status(conn, gargling_id=user.id)
    as_dict = {row["service"]: dict(row) for row in data}
    assert as_dict[service_name]["enable_steps"] is enable


def test_body_reports0():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
        {"elapsed": None, "weight": 100, "fat": 10, "first_name": "name2"},
    ]
    report = health.health.body_details(data_in)
    expected = [
        # "name1 har ikke veid seg på *365* dager. Skjerpings! ",
        "name2 veier *100* kg. Body fat percentage er *10*. ",
    ]
    assert report == expected


def test_body_reports1():
    data_in = [
        {"elapsed": None, "weight": None, "fat": None, "first_name": "name1"},
        {"elapsed": None, "weight": None, "fat": None, "first_name": "name2"},
    ]
    report = health.health.body_details(data_in)
    assert report == []


def test_body_reports2():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
    ]
    report = health.health.body_details(data_in)
    # expected = ["name1 har ikke veid seg på *365* dager. Skjerpings! "]
    assert report == []


def test_body_reports3():
    data_in = [
        {"elapsed": None, "weight": 100, "fat": None, "first_name": "name1"},
    ]
    report = health.health.body_details(data_in)
    expected = ["name1 veier *100* kg. "]
    assert report == expected


def test_body_reports4():
    data_in = [
        {"elapsed": None, "weight": None, "fat": 10, "first_name": "name1"},
    ]
    report = health.health.body_details(data_in)
    expected = ["name1 sin body fat percentage er *10*. "]
    assert report == expected


def test_activity(conn):
    user1 = conftest.users[0]
    test_fitbit.register_user(user1, conn, enable_steps=True)
    user2 = conftest.users[1]
    test_fitbit.register_user(user2, conn, enable_steps=False)
    test_date = pendulum.Date(2020, 1, 2)
    health.activity(conn, test_date)


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_health_status(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn
):
    user = conftest.users[0]
    mock_jwt_identity.return_value = user.id
    test_fitbit.register_user(user, conn)
    response = client.get("/health_status")
    assert response.json == {
        "data": {
            "fitbit": {
                "enable_steps": False,
                "enable_weight": False,
                "service": "fitbit",
            },
            "is_reminder_user": False,
        }
    }


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_health_status_toggle_reminder(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn
):
    user = conftest.users[0]
    mock_jwt_identity.return_value = user.id
    test_fitbit.register_user(user, conn)
    response = client.post("/toggle_sync_reminder", json={"enable": True})
    response = client.get("/health_status")
    assert response.json["data"]["is_reminder_user"] is True
    response = client.post("/toggle_sync_reminder", json={"enable": False})
    response = client.get("/health_status")
    assert response.json["data"]["is_reminder_user"] is False


@dataclass
class FakeResponse:
    data: dict


@dataclass
class FakeSlack:
    resp: t.Optional[FakeResponse] = None
    n_sent: int = 0

    def chat_postMessage(self, channel, text):
        self.text = text
        self.channel = channel
        self.n_sent += 1
        return self.resp

    def chat_delete(self, channel, ts):
        pass


def test_send_sync_reminders(conn):
    user = conftest.users[0]
    test_fitbit.register_user(user, conn)
    health.queries.toggle_sync_reminding(conn, enable_=True, id=user.id)
    amount = 1778
    steps_data = [
        {"gargling_id": user.id, "amount": amount},
        {"gargling_id": 0, "amount": 0},
    ]
    ts = "1503435956.000247"
    slack_client = FakeSlack(FakeResponse({"ok": True, "ts": ts}))
    health.health.send_sync_reminders(conn, slack_client, steps_data)

    assert slack_client.n_sent == 1
    assert slack_client.text == (
        f"Du gikk {amount} skritt i går, by my preliminary calculations. "
        "Husk å synce hvis dette tallet er for lavt. "
        f"Denne reminderen kan skrus av <{config.server_name}/health|her>. "
        "Stay beautiful, doll-face!"
    )
    assert slack_client.channel == user.slack_id

    reminder_users = health.queries.get_sync_reminder_users(conn)
    assert len(reminder_users) == 1
    assert dict(reminder_users[0]) == {
        "id": user.id,
        "last_sync_reminder_ts": ts,
        "slack_id": "s_id2",
    }


def test_delete_sync_reminder(conn):
    user = conftest.users[0]
    test_fitbit.register_user(user, conn)
    health.queries.toggle_sync_reminding(conn, enable_=True, id=user.id)
    health.queries.update_reminder_ts(conn, ts="1612968090.000100", id=user.id)
    slack_client = FakeSlack()
    health.health.delete_sync_reminders(conn, slack_client)
    reminder_users = health.queries.get_sync_reminder_users(conn)
    assert len(reminder_users) == 1
    assert dict(reminder_users[0]) == {
        "id": user.id,
        "last_sync_reminder_ts": None,
        "slack_id": "s_id2",
    }
