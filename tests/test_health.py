#! /usr/bin/env python3.6
# coding: utf-8
from unittest.mock import Mock, patch

import pendulum
import pytest
from flask import testing
from psycopg2.extensions import connection

from dataclasses import asdict
from gargbot_3000 import health
from tests import conftest
from tests.test_server import client


def test_authorize_user(client: testing.FlaskClient):
    health.setup_bluebrint()
    response = client.get("/fitbit-auth")
    assert response.status_code == 302
    assert response.location.startswith("https://www.fitbit.com/oauth2/authorize")


def test_handle_redirect(client: testing.FlaskClient, db_connection: connection):
    fake_user_id = "1FDG"
    fake_token = {
        "user_id": fake_user_id,
        "access_token": "das234ldkjføalsd234fj",
        "refresh_token": "f31a3slne34wlk3j4d34s3fl4kjshf",
        "expires_at": 1573921366.6757,
    }
    with patch("gargbot_3000.health.blueprint.fitbit") as mock_fitbit:
        mock_fitbit.client.session.token = fake_token
        response = client.get("/fitbit-redirect", query_string={"code": "123"})
    assert response.status_code == 302
    with db_connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fitbit where fitbit_id = %(fake_user_id)s",
            {"fake_user_id": fake_user_id},
        )
        data = cursor.fetchone()
    assert data.pop("db_id") is None
    data["user_id"] = data.pop("fitbit_id")
    assert data == fake_token


@patch.object(health, "Fitbit")
@patch.object(health, "get_weight")
@patch.object(health, "get_activity")
@patch.object(health, "get_sleep")
@patch.object(health, "get_heartrate")
def test_report_no_args(
    mock_Fitbit: Mock,
    mock_get_heartrate: Mock,
    mock_get_sleep: Mock,
    mock_get_activity: Mock,
    mock_get_weight: Mock,
    db_connection: connection,
):
    response, invalid_args, users_nonauthed = health.report(
        args=[], connection=db_connection
    )
    print(health.Fitbit)
    assert len(invalid_args) == 0
    assert len(users_nonauthed) == 0
    assert len(response) == 4
    for user_resp in response.values():
        assert len(user_resp) == 3


@pytest.mark.parametrize("users", [[], ["slack_nick2"], ["slack_nick2", "slack_nick3"]])
@pytest.mark.parametrize(
    "invalid_args", [[], ["inv_args1"], ["inv_args1", "inv_args2"]]
)
@pytest.mark.parametrize("topics", [[], ["vekt"], ["vekt", "søvn"]])
@pytest.mark.parametrize(
    "non_authed", [[], ["slack_nick6"], ["slack_nick6", "slack_nick7"]]
)
def test_parse_report_args(users, invalid_args, topics, non_authed):
    all_topics = ["vekt", "aktivitet", "søvn", "puls"]
    all_users = {user.slack_nick: user.db_id for user in conftest.users}
    all_fitbit_users = {
        user.db_id: asdict(user)
        for user in conftest.fitbit_users
        if user.db_id is not None
    }
    res = health.parse_report_args(
        args=(users + invalid_args + topics + non_authed),
        all_topics=all_topics,
        all_users=all_users,
        all_fitbit_users=all_fitbit_users,
    )
    assert res[0] == topics
    tokens = {nick: all_fitbit_users[all_users[nick]] for nick in users}
    assert res[1] == tokens
    assert res[2] == non_authed
    assert res[3] == invalid_args


@patch.object(health, "Fitbit")
def test_daily_report(mock_Fitbit: Mock, db_connection: connection):
    instance1 = Mock()
    instance2 = Mock()
    mock_Fitbit.side_effect = [instance1, instance2]
    instance1.get_bodyweight.return_value = {
        "weight": [{"date": "2000-01-02", "time": "10:11:12", "weight": 50}]
    }
    instance2.get_bodyweight.return_value = {
        "weight": [
            {"date": pendulum.now().to_date_string(), "time": "10:11:12", "weight": 100}
        ]
    }
    response = health.send_daily_report(db_connection)
    print(response)
    num_users = 2
    assert len(response["blocks"]) == num_users + 1
    assert any("*100* kg" in block["text"]["text"] for block in response["blocks"])
    assert all("*50* kg" not in block["text"]["text"] for block in response["blocks"])
