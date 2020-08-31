#! /usr/bin/env python3
# coding: utf-8
from types import SimpleNamespace
from unittest.mock import patch

from flask import testing
from google.oauth2.credentials import Credentials
import pendulum
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.health import queries
from gargbot_3000.health.googlefit import GooglefitService, GooglefitUser
from tests import conftest


def googlefit_user(conn) -> GooglefitUser:
    user = conftest.users[0]
    googlefit_user = register_user(user, conn, enable_report=True)
    return googlefit_user


expiry = pendulum.tomorrow().timestamp()


def fake_token(user) -> Credentials:
    cred = Credentials(
        token=f"access_token{user.id}",
        refresh_token=f"refresh_token{user.id}",
        client_id=config.googlefit_client_id,
        client_secret=config.googlefit_client_secret,
        token_uri="token_uri",
    )
    cred.expiry = pendulum.from_timestamp(expiry)
    return cred


def register_user(user, conn: connection, enable_report=False) -> GooglefitUser:
    token = fake_token(user)
    service_user_id = GooglefitService.insert_token(token, conn)
    queries.match_ids(
        conn, service_user_id=service_user_id, gargling_id=user.id, service="googlefit",
    )
    if enable_report:
        queries.toggle_report(
            conn, enable_=True, gargling_id=user.id, service="googlefit"
        )
    googlefit_user = GooglefitUser(
        gargling_id=user.id,
        first_name=user.first_name,
        access_token=token.token,
        refresh_token=token.refresh_token,
        expires_at=token.expiry.timestamp(),
        service_user_id=service_user_id,
    )
    return googlefit_user


def test_persist_token(conn: connection):
    user = conftest.users[0]
    register_user(user, conn)
    with conn.cursor() as cur:
        cur.execute("select * from googlefit_token")
        tokens = cur.fetchall()
        cur.execute("select * from googlefit_token_gargling")
        matched = cur.fetchall()
    assert len(tokens) == 1
    token = dict(tokens[0])
    id1 = token.pop("id")
    exp = {
        "access_token": "access_token2",
        "refresh_token": "refresh_token2",
        "expires_at": expiry,
        "enable_report": False,
    }
    assert token == exp
    assert len(matched) == 1
    match = dict(matched[0])
    id2 = match.pop("googlefit_id")
    exp = {"gargling_id": 2}
    assert match == exp
    assert id1 == id2


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.users[2]
    mock_jwt_identity.return_value = user.id
    response = client.get("googlefit/auth")
    assert response.status_code == 200
    assert response.json["auth_url"].startswith(
        "https://accounts.google.com/o/oauth2/auth"
    )


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection
):
    user = conftest.users[0]
    register_user(user, conn)
    mock_jwt_identity.return_value = user.id
    response = client.get("googlefit/auth")
    assert response.status_code == 200
    assert "report_enabled" in response.json


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect_reregister(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[0]
    h_user = register_user(user, conn)
    token = fake_token(user)
    service_user_id = queries.service_user_id_for_gargling_id(
        conn, gargling_id=user.id, service=GooglefitService.name
    )["service_user_id"]
    mock_jwt_identity.return_value = h_user.gargling_id
    with patch("gargbot_3000.health.googlefit.GooglefitService.token") as mock_handler:
        mock_handler.return_value = None, token
        response = client.get("/googlefit/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM googlefit_token where id = %(fake_user_id)s",
            {"fake_user_id": service_user_id},
        )
        data = cursor.fetchone()
    assert data["access_token"] == token.token
    assert data["refresh_token"] == token.refresh_token
    assert pendulum.from_timestamp((data["expires_at"])) == token.expiry
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT gargling_id "
            f"FROM googlefit_token_gargling where googlefit_id = %(fake_user_id)s",
            {"fake_user_id": service_user_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == h_user.gargling_id


def test_googlefit_steps(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    return_value = {
        "bucket": [
            {
                "startTimeMillis": "1598220000000",
                "endTimeMillis": "1598306400000",
                "dataset": [
                    {
                        "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:aggregated",
                        "point": [{"value": [{"intVal": 12343}]}],
                    }
                ],
            }
        ]
    }
    self = SimpleNamespace(_steps_api_call=lambda start_ms, end_ms: return_value)
    steps = GooglefitUser.steps(self, test_date)  # type: ignore
    assert steps == 12343


def test_googlefit_steps_no_data(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    return_value = {
        "bucket": [
            {
                "startTimeMillis": "1598220000000",
                "endTimeMillis": "1598306400000",
                "dataset": [
                    {
                        "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:aggregated",
                        "point": [],
                    }
                ],
            }
        ]
    }
    self = SimpleNamespace(_steps_api_call=lambda start_ms, end_ms: return_value)
    steps = GooglefitUser.steps(self, test_date)  # type: ignore
    assert steps is None
