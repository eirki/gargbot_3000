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
            "SELECT * FROM fitbit_tokens where fitbit_id = %(fake_user_id)s",
            {"fake_user_id": fake_user_id},
        )
        data = cursor.fetchone()
    data["user_id"] = data.pop("fitbit_id")
    assert data == fake_token


def test_who_is_you_bare(client: testing.FlaskClient):
    response = client.get("/whoisyou")
    assert response.status_code == 404


def test_who_is_you_incorrect(client: testing.FlaskClient):
    response = client.get("/whoisyou/incorrect")
    assert response.status_code == 403


def test_who_is_you_correct(client: testing.FlaskClient):
    response = client.get("/whoisyou/fitbit_id1")
    assert response.status_code == 200


@pytest.mark.parametrize("use_report", ["no", "yes"])
def test_who_is_you_form(
    client: testing.FlaskClient, db_connection: connection, use_report: str
):
    fitbut_user = conftest.fitbit_users[1]
    print(fitbut_user)
    form = health.WhoIsForm()
    form.name.data = fitbut_user.db_id
    form.report.data = use_report
    response = client.post(f"/whoisyou/{fitbut_user.fitbit_id}", data=form.data)
    assert response.status_code == 200
    slack_nick = next(
        user.slack_nick for user in conftest.users if user.db_id == fitbut_user.db_id
    )
    tokens = health.queries.get_fitbit_tokens_by_slack_nicks(
        db_connection, slack_nicks=[slack_nick]
    )
    assert len(tokens) == 1
    daily_tokens = health.queries.get_daily_report_tokens(db_connection)
    print(daily_tokens)
    if use_report == "no":
        assert not any(
            token["fitbit_id"] == fitbut_user.fitbit_id for token in daily_tokens
        )
    else:
        assert (
            sum(token["fitbit_id"] == fitbut_user.fitbit_id for token in daily_tokens)
            == 1
        )
    assert response.data == b"Fumbs up!"


def test_who_is_you_reask(client: testing.FlaskClient, db_connection: connection):
    fitbut_user = conftest.fitbit_users[2]
    print(fitbut_user)
    form = health.WhoIsForm()
    form.name.data = ""
    response = client.post(
        f"/whoisyou/{fitbut_user.fitbit_id}", data=form.data, follow_redirects=True
    )
    assert response.data != b"Fumbs up!"
    assert b"<form " in response.data


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
    response, invalid_args, users_nonauthed = health.report(args=[], conn=db_connection)
    print(response)
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
def test_parse_report_args(
    users, invalid_args, topics, non_authed, db_connection: connection
):
    args = users + invalid_args + topics + non_authed
    if len(args) == 0:
        return
    all_topics = {"vekt", "aktivitet", "søvn", "puls"}

    db_to_nick = {user.db_id: user.slack_nick for user in conftest.users}
    tokens = []
    for user in conftest.fitbit_users:
        if user.db_id is None:
            continue
        token = asdict(user)
        slack_nick = db_to_nick[token.pop("db_id")]
        if slack_nick not in users:
            continue
        token["slack_nick"] = slack_nick
        tokens.append(token)

    res = health.parse_report_args(conn=db_connection, args=args, all_topics=all_topics)
    assert res[0] == set(topics)
    assert res[1] == tokens
    assert res[2] == set(non_authed)
    assert res[3] == set(invalid_args)


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
    response = health.get_daily_report(db_connection)
    assert response is not None
    print(response)
    num_users = 2
    assert len(response["blocks"]) == num_users + 1
    assert any("*100* kg" in block["text"]["text"] for block in response["blocks"])
    assert all("*50* kg" not in block["text"]["text"] for block in response["blocks"])
