#! /usr/bin/env python3.6
# coding: utf-8
from unittest.mock import Mock, patch

import arrow
from flask import testing
import pendulum
from psycopg2.extensions import connection
import pytest
from withings_api.common import (
    Credentials,
    MeasureGetActivityActivity,
    MeasureGetActivityResponse,
)

from gargbot_3000 import health
from tests import conftest

services = ("service", ["withings", "fitbit"])

fake_tokens = {
    "fitbit": (
        conftest.users[3],
        "1FDG",
        {
            "user_id": "1FDG",
            "access_token": "das234ldkjføalsd234fj",
            "refresh_token": "f31a3slne34wlk3j4d34s3fl4kjshf",
            "expires_at": 1573921366.6757,
        },
    ),
    "withings": (
        conftest.users[7],
        1234,
        Credentials(
            userid=1234,
            access_token="das234ldkjføalsd234fj",
            refresh_token="f31a3slne34wlk3j4d34s3fl4kjshf",
            token_expiry=1573921366,
            client_id="withings_client_id",
            consumer_secret="withings_consumer_secret",
            token_type="Bearer",
        ),
    ),
}


def returns_value(return_value):
    def inner(*args, **kwargs):
        return return_value

    return inner


@pytest.mark.parametrize(*services)
@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, service: str, client: testing.FlaskClient
):
    user = {"fitbit": conftest.users[3], "withings": conftest.users[7]}[service]
    mock_jwt_identity.return_value = user.id
    response = client.get(f"{service}/auth")
    assert response.status_code == 200
    urls = {
        "withings": "https://account.withings.com/oauth2_user/authorize2",
        "fitbit": "https://www.fitbit.com/oauth2/authorize",
    }
    assert response.json["auth_url"].startswith(urls[service])


@pytest.mark.parametrize(*services)
@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, service: str, client: testing.FlaskClient
):
    user = {"fitbit": conftest.health_users[0], "withings": conftest.health_users[4]}[
        service
    ]
    mock_jwt_identity.return_value = user.gargling_id
    response = client.get(f"{service}/auth")
    assert response.status_code == 200
    assert "report_enabled" in response.json


@pytest.mark.parametrize(*services)
@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect(
    mock_jwt_required,
    mock_jwt_identity,
    service: str,
    client: testing.FlaskClient,
    conn: connection,
):
    user, fake_id, fake_token = fake_tokens[service]
    mock_jwt_identity.return_value = user.id
    with patch(f"gargbot_3000.health.{service.capitalize()}.token") as mock_handler:
        mock_handler.return_value = fake_id, fake_token
        response = client.get(f"/{service}/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, access_token, refresh_token, expires_at "
            f"FROM {service}_token where id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    if service == "fitbit":
        assert data["id"] == fake_id
        assert data["access_token"] == fake_token["access_token"]
        assert data["refresh_token"] == fake_token["refresh_token"]
        assert data["expires_at"] == fake_token["expires_at"]
    elif service == "withings":
        assert data["id"] == fake_token.userid
        assert data["access_token"] == fake_token.access_token
        assert data["refresh_token"] == fake_token.refresh_token
        assert data["expires_at"] == fake_token.token_expiry
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT gargling_id "
            f"FROM {service}_token_gargling where {service}_id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == user.id


@pytest.mark.parametrize(*services)
@pytest.mark.parametrize("enable", [True, False])
@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_toggle_report(
    mock_jwt_required,
    mock_jwt_identity,
    service: str,
    enable: bool,
    client: testing.FlaskClient,
    conn: connection,
):
    offset = 0 if not enable else 1
    user = {
        "fitbit": conftest.health_users[0 + offset],
        "withings": conftest.health_users[4 + offset],
    }[service]
    data = health.queries.is_registered(
        conn, gargling_id=user.gargling_id, service=service
    )
    assert user.enable_report is not enable
    assert data["enable_report"] is not enable

    mock_jwt_identity.return_value = user.gargling_id
    response = client.post(
        "/toggle_report", json={"service": service, "enable": enable}
    )
    assert response.status_code == 200

    data = health.queries.is_registered(
        conn, gargling_id=user.gargling_id, service=service
    )
    assert data["enable_report"] is enable


@patch.object(health, "WithingsApi")
def test_withings_steps(mock_Withings: Mock, conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    withings_instance1 = Mock()
    none_data = {
        "timezone": None,
        "deviceid": None,
        "brand": None,
        "is_tracker": None,
        "distance": None,
        "elevation": None,
        "soft": None,
        "moderate": None,
        "intense": None,
        "active": None,
        "calories": None,
        "totalcalories": None,
        "hr_average": None,
        "hr_min": None,
        "hr_max": None,
        "hr_zone_0": None,
        "hr_zone_1": None,
        "hr_zone_2": None,
        "hr_zone_3": None,
    }
    n_steps = 6620
    withings_instance1.measure_get_activity.return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(date=test_date, steps=n_steps, **none_data),
        ),
        more=False,
        offset=0,
    )
    mock_Withings.side_effect = [withings_instance1]
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token)
        for token in tokens
        if token["service"] == "withings"
    ]
    assert len(users) == 1
    user = users[0]
    steps = user.steps(test_date)
    assert steps == n_steps


@patch.object(health, "WithingsApi")
def test_withings_steps_no_data(mock_Withings: Mock, conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    withings_instance1 = Mock()
    none_data = {
        "timezone": None,
        "deviceid": None,
        "brand": None,
        "is_tracker": None,
        "distance": None,
        "elevation": None,
        "soft": None,
        "moderate": None,
        "intense": None,
        "active": None,
        "calories": None,
        "totalcalories": None,
        "hr_average": None,
        "hr_min": None,
        "hr_max": None,
        "hr_zone_0": None,
        "hr_zone_1": None,
        "hr_zone_2": None,
        "hr_zone_3": None,
    }
    withings_instance1.measure_get_activity.return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(
                date=arrow.get(test_date.subtract(days=1)), steps=123, **none_data
            ),
        ),
        more=False,
        offset=0,
    )
    mock_Withings.side_effect = [withings_instance1]
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token)
        for token in tokens
        if token["service"] == "withings"
    ]
    assert len(users) == 1
    user = users[0]
    steps = user.steps(test_date)
    assert steps is None


@patch.object(health, "FitbitApi")
def test_fitbit_steps(mock_Fitbit: Mock, conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    fitbit_instance1, fitbit_instance2 = Mock(), Mock()
    fitbit_instance1.time_series.return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13475"},
            {"dateTime": "2019-12-29", "value": "1"},
        ]
    }
    fitbit_instance2.time_series.return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13474"},
            {"dateTime": "2020-01-02", "value": "86"},
        ]
    }
    mock_Fitbit.side_effect = [fitbit_instance1, fitbit_instance2]
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token)
        for token in tokens
        if token["service"] == "fitbit"
    ]
    assert len(users) == 2
    steps = [user.steps(test_date) for user in users]
    assert steps == [13475, 13474]


@patch.object(health, "FitbitApi")
def test_fitbit_steps_no_data(mock_Fitbit: Mock, conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    fitbit_instance1, fitbit_instance2 = Mock(), Mock()
    fitbit_instance1.time_series.return_value = {"activities-steps": []}
    fitbit_instance2.time_series.return_value = {"activities-steps": []}
    mock_Fitbit.side_effect = [fitbit_instance1, fitbit_instance2]
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token)
        for token in tokens
        if token["service"] == "fitbit"
    ]
    assert len(users) == 2
    steps = [user.steps(test_date) for user in users]
    assert steps == [None, None]


@patch.object(health, "FitbitApi")
def test_fitbit_body(mock_Fitbit: Mock, conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    fitbit_instance1, fitbit_instance2 = Mock(), Mock()
    fitbit_instance1.get_bodyweight.return_value = {
        "weight": [{"date": "2019-01-02", "time": "10:11:12", "weight": 50}]
    }
    fitbit_instance1.get_bodyfat.return_value = {
        "fat": [{"date": "2019-01-02", "time": "10:11:12", "fat": 5}]
    }
    fitbit_instance2.get_bodyweight.return_value = {
        "weight": [
            {"date": "2020-01-01", "time": "10:11:12", "weight": 75},
            {"date": "2020-01-02", "time": "10:11:12", "weight": 100},
        ]
    }
    fitbit_instance2.get_bodyfat.return_value = {
        "fat": [
            {"date": "2020-01-01", "time": "10:11:12", "fat": 7},
            {"date": "2020-01-02", "time": "10:11:12", "fat": 10},
        ]
    }
    mock_Fitbit.side_effect = [fitbit_instance1, fitbit_instance2]
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token)
        for token in tokens
        if token["service"] == "fitbit"
    ]
    assert len(users) == 2
    data = [user.body(test_date) for user in users]
    expected = [
        {"elapsed": 365, "weight": None, "fat": None},
        {"elapsed": None, "weight": 100, "fat": 10},
    ]
    assert data == expected


@patch.object(health, "FitbitApi")
def test_fitbit_body_no_data(mock_Fitbit: Mock, conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    fitbit_instance1, fitbit_instance2 = Mock(), Mock()
    fitbit_instance1.get_bodyweight.return_value = {"weight": []}
    fitbit_instance1.get_bodyfat.return_value = {"fat": []}
    fitbit_instance2.get_bodyweight.return_value = {"weight": []}
    fitbit_instance2.get_bodyfat.return_value = {"fat": []}
    mock_Fitbit.side_effect = [fitbit_instance1, fitbit_instance2]
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token)
        for token in tokens
        if token["service"] == "fitbit"
    ]
    assert len(users) == 2
    data = [user.body(test_date) for user in users]
    expected = [
        {"elapsed": None, "fat": None, "weight": None},
        {"elapsed": None, "fat": None, "weight": None},
    ]
    assert data == expected


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
            {"date": "2020-01-02", "active-steps": 1500},
            {"date": "2020-01-02", "active-steps": 1500},
        ]
    )
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token) for token in tokens if token["service"] == "polar"
    ]
    assert len(users) == 1
    user = users[0]
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 3000


def test_polar_steps_cached(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans([{"date": "2020-01-02", "active-steps": 1000}])
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token) for token in tokens if token["service"] == "polar"
    ]
    assert len(users) == 1
    user = users[0]
    to_cache = [
        {"taken_at": test_date, "n_steps": 1500, "gargling_id": user.gargling_id}
    ]
    health.queries.upsert_steps(conn, to_cache)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 2500


def test_polar_steps_multiple_dates(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {"date": "2020-01-01", "active-steps": 1500},
            {"date": "2020-01-02", "active-steps": 1501},
            {"date": "2020-01-03", "active-steps": 1502},
        ]
    )
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token) for token in tokens if token["service"] == "polar"
    ]
    assert len(users) == 1
    user = users[0]
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1501


def test_polar_steps_future_cached(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {"date": "2020-01-02", "active-steps": 1501},
            {"date": "2020-01-03", "active-steps": 1502},
        ]
    )
    tokens = health.queries.tokens(conn)
    users = [
        health.HealthUser.init(token) for token in tokens if token["service"] == "polar"
    ]
    assert len(users) == 1
    user = users[0]
    user._get_transaction = lambda: tran  # type: ignore
    user.steps(test_date, conn)
    future = test_date.add(days=1)
    cached = health.queries.cached_step_for_date(conn, date=future, id=user.gargling_id)
    assert cached["n_steps"] == 1502


def test_body_reports0():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
        {"elapsed": None, "weight": 100, "fat": 10, "first_name": "name2"},
    ]
    report = health.body_details(data_in)
    expected = [
        # "name1 har ikke veid seg på *365* dager. Skjerpings! ",
        "name2 veier *100* kg. Body fat percentage er *10*",
    ]
    assert report == expected


def test_body_reports1():
    data_in = [
        {"elapsed": None, "weight": None, "fat": None, "first_name": "name1"},
        {"elapsed": None, "weight": None, "fat": None, "first_name": "name2"},
    ]
    report = health.body_details(data_in)
    assert report == []


def test_body_reports2():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
    ]
    report = health.body_details(data_in)
    # expected = ["name1 har ikke veid seg på *365* dager. Skjerpings! "]
    assert report == []


def test_body_reports3():
    data_in = [
        {"elapsed": None, "weight": 100, "fat": None, "first_name": "name1"},
    ]
    report = health.body_details(data_in)
    expected = ["name1 veier *100* kg. "]
    assert report == expected


def test_body_reports4():
    data_in = [
        {"elapsed": None, "weight": None, "fat": 10, "first_name": "name1"},
    ]
    report = health.body_details(data_in)
    expected = ["name1 sin body fat percentage er *10*. "]
    assert report == expected
