#! /usr/bin/env python3
# coding: utf-8
from unittest.mock import patch

from flask import testing
import pendulum
from psycopg2.extensions import connection

from gargbot_3000.health import queries
from gargbot_3000.health.polar import PolarService, PolarUser
from tests import conftest


def fake_token(user):
    return {
        "x_user_id": user.id * 1000,
        "access_token": f"access_token{user.id}",
    }


def register_user(user, conn: connection, enable_report=False) -> PolarUser:
    token = fake_token(user)
    PolarService.persist_token(token, conn)
    queries.match_ids(
        conn, service_user_id=token["x_user_id"], gargling_id=user.id, service="polar",
    )
    if enable_report:
        queries.toggle_report(conn, enable_=True, gargling_id=user.id, service="polar")
    polar_user = PolarUser(
        gargling_id=user.id,
        first_name=user.first_name,
        access_token=token["access_token"],
        refresh_token=None,
        expires_at=None,
        service_user_id=token["x_user_id"],
    )
    return polar_user


def test_persist_token(conn: connection):
    user = conftest.users[0]
    register_user(user, conn)
    with conn.cursor() as cur:
        cur.execute("select * from polar_token")
        tokens = cur.fetchall()
        cur.execute("select * from polar_token_gargling")
        matched = cur.fetchall()
    assert len(tokens) == 1
    token = dict(tokens[0])
    exp = {
        "id": user.id * 1000,
        "access_token": "access_token2",
        "refresh_token": None,
        "expires_at": None,
        "enable_report": False,
    }
    assert token == exp
    assert len(matched) == 1
    match = dict(matched[0])
    exp = {"polar_id": user.id * 1000, "gargling_id": 2}
    assert match == exp


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.users[0]
    mock_jwt_identity.return_value = user.id
    response = client.get("polar/auth")
    assert response.status_code == 200
    assert response.json["auth_url"].startswith(
        "https://flow.polar.com/oauth2/authorization"
    )


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[0]
    register_user(user, conn)
    mock_jwt_identity.return_value = user.id
    response = client.get("polar/auth")
    assert response.status_code == 200
    assert "report_enabled" in response.json


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.users[0]
    token = fake_token(user)
    fake_id = token["x_user_id"]
    mock_jwt_identity.return_value = user.id
    with patch("gargbot_3000.health.polar.PolarService.token") as mock_handler:
        mock_handler.return_value = fake_id, token
        response = client.get("/polar/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM polar_token where id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["id"] == fake_id
    assert data["access_token"] == token["access_token"]
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM polar_token_gargling where polar_id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == user.id


def polar_user(conn):
    user = conftest.users[0]
    health_user = register_user(user, conn, enable_report=True)
    return health_user


class FakePolarTrans:
    def __init__(self, activities):
        self.activities = {i: act for i, act in enumerate(activities)}

    def list_activities(self):
        return {"activity-log": self.activities.keys()}

    def get_activity_summary(self, activity):
        return self.activities[activity]

    def commit(self):
        pass


def test_polar_steps(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {
                "date": "2020-01-02",
                "created": "2020-01-02T20:11:33.000Z",
                "active-steps": 1500,
            }
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1500


def test_polar_steps_cached(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    user = polar_user(conn)
    to_cache = [
        {
            "taken_at": pendulum.Date(2020, 1, 2),
            "created_at": pendulum.datetime(2020, 1, 2, 0, 0, 0),
            "n_steps": 1000,
            "gargling_id": user.gargling_id,
        }
    ]
    queries.upsert_steps(conn, to_cache)
    tran = FakePolarTrans(
        [
            {
                "date": "2020-01-02",
                "created": "2020-01-02T20:11:33.000Z",
                "active-steps": 1500,
            }
        ]
    )
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1500


def test_polar_steps_multiple_dates(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {
                "date": "2020-01-01",
                "created": "2020-01-01T20:11:33.000Z",
                "active-steps": 1500,
            },
            {
                "date": "2020-01-02",
                "created": "2020-01-02T20:11:33.000Z",
                "active-steps": 1501,
            },
            {
                "date": "2020-01-03",
                "created": "2020-01-03T20:11:33.000Z",
                "active-steps": 1502,
            },
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1501


def test_polar_steps_multiple_same_date(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {
                "date": "2020-01-02",
                "created": "2020-01-02T16:11:33.000Z",
                "active-steps": 1499,
            },
            {
                "date": "2020-01-02",
                "created": "2020-01-02T20:11:33.000Z",
                "active-steps": 1501,
            },
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1501


def test_polar_steps_multiple_same_date_different_created(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {
                "date": "2020-01-02",
                "created": "2020-01-02T16:11:33.000Z",
                "active-steps": 1499,
            },
            {
                "date": "2020-01-02",
                "created": "2020-01-02T20:11:33.000Z",
                "active-steps": 1501,
            },
            {
                "date": "2020-01-03",
                "created": "2020-01-02T23:11:33.000Z",
                "active-steps": 1504,
            },
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1501


def test_polar_steps_future_cached(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {
                "date": "2020-01-02",
                "created": "2020-01-02T20:11:33.000Z",
                "active-steps": 1501,
            },
            {
                "date": "2020-01-03",
                "created": "2020-01-03T20:11:33.000Z",
                "active-steps": 1502,
            },
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    user.steps(test_date, conn)
    future = test_date.add(days=1)
    cached = queries.cached_step_for_date(conn, date=future, id=user.gargling_id)
    assert cached["n_steps"] == 1502
