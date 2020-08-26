#! /usr/bin/env python3
# coding: utf-8
import typing as t
from unittest.mock import patch

from flask import testing
import pendulum
from psycopg2.extensions import connection

from gargbot_3000.health import queries
from gargbot_3000.health.fitbit_ import FitbitUser
from tests import conftest


@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.users[3]
    mock_jwt_identity.return_value = user.id
    response = client.get("fitbit/auth")
    assert response.status_code == 200
    assert response.json["auth_url"].startswith(
        "https://www.fitbit.com/oauth2/authorize"
    )


@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.health_users[0]
    mock_jwt_identity.return_value = user.gargling_id
    response = client.get("fitbit/auth")
    assert response.status_code == 200
    assert "report_enabled" in response.json


@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[3]
    fake_id = "1FDG"
    fake_token = {
        "user_id": "1FDG",
        "access_token": "das234ldkjføalsd234fj",
        "refresh_token": "f31a3slne34wlk3j4d34s3fl4kjshf",
        "expires_at": 1573921366.6757,
    }
    mock_jwt_identity.return_value = user.id
    with patch("gargbot_3000.health.fitbit_.FitbitService.token") as mock_handler:
        mock_handler.return_value = fake_id, fake_token
        response = client.get("/fitbit/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, access_token, refresh_token, expires_at "
            f"FROM fitbit_token where id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["id"] == fake_id
    assert data["access_token"] == fake_token["access_token"]
    assert data["refresh_token"] == fake_token["refresh_token"]
    assert data["expires_at"] == fake_token["expires_at"]
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT gargling_id "
            f"FROM fitbit_token_gargling where fitbit_id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == user.id


def fitbit_users(conn):
    tokens = queries.tokens(conn)
    tokens = [dict(token) for token in tokens]
    users = [
        FitbitUser(**token) for token in tokens if token.pop("service") == "fitbit"
    ]
    assert len(users) == 2
    return users


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
    user1._steps_api_call = lambda date: user1_return_value
    user2._steps_api_call = lambda date: user2_return_value
    test_date = pendulum.Date(2020, 1, 2)
    steps = [user.steps(test_date) for user in users]
    assert steps == [13475, 13474]


def test_fitbit_steps_no_data(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_return_value: t.Dict[str, list] = {"activities-steps": []}
    user2_return_value: t.Dict[str, list] = {"activities-steps": []}
    user1._steps_api_call = lambda date: user1_return_value
    user2._steps_api_call = lambda date: user2_return_value
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
    user1._weight_api_call = lambda date: user1_weight_return_value
    user1._bodyfat_api_call = lambda date: user1_bodyfat_return_value
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
    user2._weight_api_call = lambda date: user2_weight_return_value
    user2._bodyfat_api_call = lambda date: user2_bodyfat_return_value

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
    user1._weight_api_call = lambda date: user1_weight_return_value
    user1._bodyfat_api_call = lambda date: user1_bodyfat_return_value
    user2_weight_return_value: t.Dict[str, list] = {"weight": []}
    user2_bodyfat_return_value: t.Dict[str, list] = {"fat": []}
    user2._weight_api_call = lambda date: user2_weight_return_value
    user2._bodyfat_api_call = lambda date: user2_bodyfat_return_value
    expected = [
        {"elapsed": None, "fat": None, "weight": None},
        {"elapsed": None, "fat": None, "weight": None},
    ]
    test_date = pendulum.Date(2020, 1, 2)
    data = [user.body(test_date) for user in users]
    assert data == expected
