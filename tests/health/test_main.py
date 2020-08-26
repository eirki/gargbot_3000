#! /usr/bin/env python3
# coding: utf-8
from unittest.mock import patch

from flask import testing
from psycopg2.extensions import connection
import pytest

from gargbot_3000 import health
from tests import conftest

services = ("service", ["withings", "fitbit"])


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
    if service == "fitbit" and enable is True:
        return
        # FIXME
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
