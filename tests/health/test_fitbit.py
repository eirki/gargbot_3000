#! /usr/bin/env python3
# coding: utf-8
import typing as t
from unittest.mock import patch

from flask import testing
import pendulum
from psycopg2.extensions import connection

from gargbot_3000.health import queries
from gargbot_3000.health.fitbit_ import FitbitService, FitbitUser
from tests import conftest


def fake_token(user):
    return {
        "user_id": f"fitbit_id{user.id}",
        "access_token": f"access_token{user.id}",
        "refresh_token": f"refresh_token{user.id}",
        "expires_at": 1573921366.6757,
    }


def register_user(user, conn: connection, enable_report=False) -> FitbitUser:
    token = fake_token(user)
    FitbitService.persist_token(token, conn)
    queries.match_ids(
        conn,
        service_user_id=token["user_id"],
        gargling_id=user.id,
        token_gargling_table="fitbit_token_gargling",
    )
    if enable_report:
        queries.toggle_report(
            conn,
            enable_=True,
            gargling_id=user.id,
            token_table="fitbit_token",
            token_gargling_table="fitbit_token_gargling",
        )
    fitbit_user = FitbitUser(
        gargling_id=user.id,
        first_name=user.first_name,
        access_token=token["access_token"],
        refresh_token=token["refresh_token"],
        expires_at=token["expires_at"],
        service_user_id=token["user_id"],
    )
    return fitbit_user


def test_persist_token(conn: connection):
    user = conftest.users[0]
    register_user(user, conn)
    with conn.cursor() as cur:
        cur.execute("select * from fitbit_token")
        tokens = cur.fetchall()
        cur.execute("select * from fitbit_token_gargling")
        matched = cur.fetchall()
    assert len(tokens) == 1
    token = dict(tokens[0])
    exp = {
        "id": "fitbit_id2",
        "access_token": "access_token2",
        "refresh_token": "refresh_token2",
        "expires_at": 1573921366.6757,
        "enable_report": False,
    }
    assert token == exp
    assert len(matched) == 1
    match = dict(matched[0])
    exp = {"service_user_id": "fitbit_id2", "gargling_id": 2}
    assert match == exp


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.users[0]
    mock_jwt_identity.return_value = user.id
    response = client.get("fitbit/auth")
    assert response.status_code == 200
    assert response.json["auth_url"].startswith(
        "https://www.fitbit.com/oauth2/authorize"
    )


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[0]
    register_user(user, conn)
    mock_jwt_identity.return_value = user.id
    response = client.get("fitbit/auth")
    assert response.status_code == 200
    assert "report_enabled" in response.json


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[0]
    token = fake_token(user)
    fake_id = token["user_id"]
    mock_jwt_identity.return_value = user.id
    with patch("gargbot_3000.health.fitbit_.FitbitService.token") as mock_handler:
        mock_handler.return_value = fake_id, token
        response = client.get("/fitbit/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fitbit_token where id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["id"] == fake_id
    assert data["access_token"] == token["access_token"]
    assert data["refresh_token"] == token["refresh_token"]
    assert data["expires_at"] == token["expires_at"]
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fitbit_token_gargling where service_user_id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == user.id


def fitbit_users(conn) -> t.List[FitbitUser]:
    users = conftest.users[0:2]
    health_users = [register_user(user, conn, enable_report=True) for user in users]
    return health_users


def test_fitbit_steps(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13475"},
            {"dateTime": "2019-12-29", "value": "1"},
        ]
    }
    user2_return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13474"},
            {"dateTime": "2020-01-02", "value": "86"},
        ]
    }
    user1._steps_api_call = lambda date: user1_return_value  # type: ignore
    user2._steps_api_call = lambda date: user2_return_value  # type: ignore
    test_date = pendulum.Date(2020, 1, 2)
    steps = [user.steps(test_date) for user in users]
    assert steps == [13475, 13474]


def test_fitbit_steps_no_data(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_return_value: t.Dict[str, list] = {"activities-steps": []}
    user2_return_value: t.Dict[str, list] = {"activities-steps": []}
    user1._steps_api_call = lambda date: user1_return_value  # type: ignore
    user2._steps_api_call = lambda date: user2_return_value  # type: ignore
    test_date = pendulum.Date(2020, 1, 2)
    steps = [user.steps(test_date) for user in users]
    assert steps == [None, None]


def test_fitbit_body(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_weight_return_value = {
        "weight": [{"date": "2019-01-02", "time": "10:11:12", "weight": 50}]
    }
    user1_bodyfat_return_value = {
        "fat": [{"date": "2019-01-02", "time": "10:11:12", "fat": 5}]
    }
    user1._weight_api_call = lambda date: user1_weight_return_value  # type: ignore
    user1._bodyfat_api_call = lambda date: user1_bodyfat_return_value  # type: ignore
    user2_weight_return_value = {
        "weight": [
            {"date": "2020-01-01", "time": "10:11:12", "weight": 75},
            {"date": "2020-01-02", "time": "10:11:12", "weight": 100},
        ]
    }
    user2_bodyfat_return_value = {
        "fat": [
            {"date": "2020-01-01", "time": "10:11:12", "fat": 7},
            {"date": "2020-01-02", "time": "10:11:12", "fat": 10},
        ]
    }
    user2._weight_api_call = lambda date: user2_weight_return_value  # type: ignore
    user2._bodyfat_api_call = lambda date: user2_bodyfat_return_value  # type: ignore

    test_date = pendulum.Date(2020, 1, 2)
    data = [user.body(test_date) for user in users]
    expected = [
        {"elapsed": 365, "weight": None, "fat": None},
        {"elapsed": None, "weight": 100, "fat": 10},
    ]
    assert data == expected


def test_fitbit_body_no_data(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_weight_return_value: t.Dict[str, list] = {"weight": []}
    user1_bodyfat_return_value: t.Dict[str, list] = {"fat": []}
    user1._weight_api_call = lambda date: user1_weight_return_value  # type: ignore
    user1._bodyfat_api_call = lambda date: user1_bodyfat_return_value  # type: ignore
    user2_weight_return_value: t.Dict[str, list] = {"weight": []}
    user2_bodyfat_return_value: t.Dict[str, list] = {"fat": []}
    user2._weight_api_call = lambda date: user2_weight_return_value  # type: ignore
    user2._bodyfat_api_call = lambda date: user2_bodyfat_return_value  # type: ignore
    expected = [
        {"elapsed": None, "fat": None, "weight": None},
        {"elapsed": None, "fat": None, "weight": None},
    ]
    test_date = pendulum.Date(2020, 1, 2)
    data = [user.body(test_date) for user in users]
    assert data == expected
