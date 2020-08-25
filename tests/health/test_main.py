#! /usr/bin/env python3
# coding: utf-8
from unittest.mock import patch

from flask import testing
from psycopg2.extensions import connection
import pytest
from withings_api.common import Credentials

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


@pytest.mark.parametrize(*services)
@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_not_registered(
    mock_jwt_required, mock_jwt_identity, service: str, client: testing.FlaskClient
):
    response = client.get("/")
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
    obj = {"fitbit": "fitbit_.FitbitService", "withings": "withings.WithingsService"}
    with patch(f"gargbot_3000.health.{obj[service]}.token") as mock_handler:
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


def test_body_reports0():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
        {"elapsed": None, "weight": 100, "fat": 10, "first_name": "name2"},
    ]
    report = health.body_details(data_in)
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
