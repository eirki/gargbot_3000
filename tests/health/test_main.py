#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from unittest.mock import patch

from flask import testing
import pendulum
from psycopg2.extensions import connection
import pytest

from gargbot_3000 import health
from gargbot_3000.health import fitbit_, googlefit, polar, withings
from tests import conftest
from tests.health import test_fitbit, test_googlefit, test_polar, test_withings

modules = {
    "fitbit": (fitbit_, test_fitbit),
    "googlefit": (googlefit, test_googlefit),
    "polar": (polar, test_polar),
    "withings": (withings, test_withings),
}
services = ("service_name", ["withings", "fitbit", "googlefit", "polar"])


@pytest.mark.parametrize(*services)
@pytest.mark.parametrize("enable", [True, False])
@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_toggle_steps(
    mock_jwt_required,
    mock_jwt_identity,
    service_name: str,
    enable: bool,
    client: testing.FlaskClient,
    conn: connection,
):
    user = conftest.users[0]
    module, test_module = modules[service_name]
    test_module.register_user(user, conn, enable_steps=not enable)
    data = health.queries.health_status(conn, gargling_id=user.id)
    as_dict = {row["service"]: dict(row) for row in data}
    assert as_dict[service_name]["enable_steps"] is not enable

    mock_jwt_identity.return_value = user.id
    response = client.post(
        "/health_toggle",
        json={"measure": "steps", "service": service_name, "enable": enable},
    )
    assert response.status_code == 200

    data = health.queries.health_status(conn, gargling_id=user.id)
    as_dict = {row["service"]: dict(row) for row in data}
    assert as_dict[service_name]["enable_steps"] is enable


def test_body_reports0():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
        {"elapsed": None, "weight": 100, "fat": 10, "first_name": "name2"},
    ]
    report = health.health.body_details(data_in)
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
    report = health.health.body_details(data_in)
    assert report == []


def test_body_reports2():
    data_in = [
        {"elapsed": 365, "weight": None, "fat": None, "first_name": "name1"},
    ]
    report = health.health.body_details(data_in)
    # expected = ["name1 har ikke veid seg på *365* dager. Skjerpings! "]
    assert report == []


def test_body_reports3():
    data_in = [
        {"elapsed": None, "weight": 100, "fat": None, "first_name": "name1"},
    ]
    report = health.health.body_details(data_in)
    expected = ["name1 veier *100* kg. "]
    assert report == expected


def test_body_reports4():
    data_in = [
        {"elapsed": None, "weight": None, "fat": 10, "first_name": "name1"},
    ]
    report = health.health.body_details(data_in)
    expected = ["name1 sin body fat percentage er *10*. "]
    assert report == expected


def test_activity(conn):
    user1 = conftest.users[0]
    test_fitbit.register_user(user1, conn, enable_steps=True)
    user2 = conftest.users[1]
    test_fitbit.register_user(user2, conn, enable_steps=False)
    test_date = pendulum.Date(2020, 1, 2)
    health.activity(conn, test_date)
    # TODO: mock out body and steps calls and check results
