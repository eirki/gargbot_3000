#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import arrow
from flask import testing
import pendulum
from psycopg2.extensions import connection
from withings_api.common import (
    Credentials,
    MeasureGetActivityActivity,
    MeasureGetActivityResponse,
)

from gargbot_3000 import config
from gargbot_3000.health import queries
from gargbot_3000.health.withings import WithingsService, WithingsUser
from tests import conftest


def withings_user(conn) -> WithingsUser:
    user = conftest.users[0]
    withings_user = register_user(user, conn, enable_steps=True)
    return withings_user


def fake_token(user) -> Credentials:
    return Credentials(
        userid=user.id + 1000,
        access_token=f"access_token{user.id}",
        refresh_token=f"refresh_token{user.id}",
        token_expiry=1573921366,
        client_id=config.withings_client_id,
        consumer_secret=config.withings_consumer_secret,
        token_type="Bearer",
    )


def register_user(user, conn: connection, enable_steps=False) -> WithingsUser:
    token = fake_token(user)
    WithingsService.persist_token(token, conn)
    queries.match_ids(
        conn,
        service_user_id=token.userid,
        gargling_id=user.id,
        token_gargling_table="withings_token_gargling",
    )
    if enable_steps:
        queries.toggle_service(
            conn,
            enable_=True,
            gargling_id=user.id,
            type_col=f"enable_steps",
            token_table="withings_token",
            token_gargling_table="withings_token_gargling",
        )
    withings_user = WithingsUser(
        gargling_id=user.id,
        first_name=user.first_name,
        access_token=token.access_token,
        refresh_token=token.refresh_token,
        expires_at=token.token_expiry,
        service_user_id=token.userid,
    )
    return withings_user


def test_persist_token(conn: connection):
    user = conftest.users[0]
    register_user(user, conn)
    with conn.cursor() as cur:
        cur.execute("select * from withings_token")
        tokens = cur.fetchall()
        cur.execute("select * from withings_token_gargling")
        matched = cur.fetchall()
    assert len(tokens) == 1
    token = dict(tokens[0])
    exp = {
        "id": 1002,
        "access_token": "access_token2",
        "refresh_token": "refresh_token2",
        "expires_at": 1573921366,
        "enable_steps": False,
        "enable_weight": False,
    }
    assert token == exp
    assert len(matched) == 1
    match = dict(matched[0])
    exp = {"service_user_id": 1002, "gargling_id": 2}
    assert match == exp


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.users[5]
    mock_jwt_identity.return_value = user.id
    response = client.get("withings/auth")
    assert response.status_code == 200
    assert response.json["auth_url"].startswith(
        "https://account.withings.com/oauth2_user/authorize2"
    )


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection
):
    user = conftest.users[0]
    register_user(user, conn)
    mock_jwt_identity.return_value = user.id
    response = client.get("withings/auth")
    assert response.status_code == 200
    assert response.json["auth_url"].startswith(
        "https://account.withings.com/oauth2_user/authorize2"
    )


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[7]
    fake_id = 1234
    fake_token = Credentials(
        userid=1234,
        access_token="das234ldkjføalsd234fj",
        refresh_token="f31a3slne34wlk3j4d34s3fl4kjshf",
        token_expiry=1573921366,
        client_id="withings_client_id",
        consumer_secret="withings_consumer_secret",
        token_type="Bearer",
    )

    mock_jwt_identity.return_value = user.id
    with patch("gargbot_3000.health.withings.WithingsService.token") as mock_handler:
        mock_handler.return_value = fake_id, fake_token
        response = client.get("/withings/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, access_token, refresh_token, expires_at "
            f"FROM withings_token where id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["id"] == fake_token.userid
    assert data["access_token"] == fake_token.access_token
    assert data["refresh_token"] == fake_token.refresh_token
    assert data["expires_at"] == fake_token.token_expiry
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT gargling_id "
            f"FROM withings_token_gargling where service_user_id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == user.id


def test_withings_steps(conn: connection):
    user = withings_user(conn)
    test_date = pendulum.Date(2020, 1, 2)
    none_data = {
        "timezone": dt.tzinfo(),
        "brand": 1,
        "is_tracker": True,
        "totalcalories": 0.1,
    }
    n_steps = 6620
    return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(
                date=arrow.get(test_date), steps=n_steps, **none_data
            ),
        ),
        more=False,
        offset=0,
    )
    user._steps_api_call = lambda date: return_value  # type: ignore
    steps = user.steps(test_date)
    assert steps == n_steps


def test_withings_steps_no_data(conn: connection):
    user = withings_user(conn)
    test_date = pendulum.Date(2020, 1, 2)
    none_data = {
        "timezone": dt.tzinfo(),
        "brand": 1,
        "is_tracker": True,
        "totalcalories": 0.1,
    }
    return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(
                date=arrow.get(test_date.subtract(days=1)), steps=123, **none_data
            ),
        ),
        more=False,
        offset=0,
    )
    user._steps_api_call = lambda date: return_value  # type: ignore
    steps = user.steps(test_date)
    assert steps == 0
