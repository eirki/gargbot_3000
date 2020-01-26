#! /usr/bin/env python3.6
# coding: utf-8
from unittest.mock import Mock, patch

import arrow
import pendulum
import pytest
from flask import testing
from psycopg2.extensions import connection
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
        "1FDG",
        {
            "user_id": "1FDG",
            "access_token": "das234ldkjføalsd234fj",
            "refresh_token": "f31a3slne34wlk3j4d34s3fl4kjshf",
            "expires_at": 1573921366.6757,
        },
    ),
    "withings": (
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
def test_authorize_user(service: str, client: testing.FlaskClient):
    response = client.get(f"{service}/auth")
    assert response.status_code == 302
    urls = {
        "withings": "https://account.withings.com/oauth2_user/authorize2",
        "fitbit": "https://www.fitbit.com/oauth2/authorize",
    }
    assert response.location.startswith(urls[service])


@pytest.mark.parametrize(*services)
def test_handle_redirect(service: str, client: testing.FlaskClient, conn: connection):
    fake_id, fake_token = fake_tokens[service]
    with patch(
        f"gargbot_3000.health.{service.capitalize()}.handle_redirect"
    ) as mock_handler:
        mock_handler.return_value = fake_id, fake_token
        response = client.get(f"/{service}/redirect", query_string={"code": "123"})
    assert response.status_code == 302
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, access_token, refresh_token, expires_at "
            f"FROM {service}_token where id = %(fake_user_id)s",
            {"fake_user_id": fake_id},
        )
        data = cursor.fetchone()
    if service == "fitbit":
        assert data["id"] == fake_token["user_id"]
        assert data["access_token"] == fake_token["access_token"]
        assert data["refresh_token"] == fake_token["refresh_token"]
        assert data["expires_at"] == fake_token["expires_at"]
    elif service == "withings":
        assert data["id"] == fake_token.userid
        assert data["access_token"] == fake_token.access_token
        assert data["refresh_token"] == fake_token.refresh_token
        assert data["expires_at"] == fake_token.token_expiry


@pytest.mark.parametrize(*services)
def test_who_is_you_bare(service: str, client: testing.FlaskClient):
    response = client.get(f"whoisyou/{service}")
    assert response.status_code == 404


@pytest.mark.parametrize(*services)
def test_who_is_you_incorrect(service: str, client: testing.FlaskClient):
    response = client.get(f"whoisyou/{service}/incorrect")
    assert response.status_code == 403


@pytest.mark.parametrize(*services)
def test_who_is_you_correct(service: str, client: testing.FlaskClient):
    service_user_id = 106 if service == "withings" else "fitbit_id2"
    response = client.get(f"whoisyou/{service}/{service_user_id}")
    assert response.status_code == 200


@pytest.mark.parametrize("use_report", ["no", "yes"])
@pytest.mark.parametrize(*services)
def test_who_is_you_form(
    client: testing.FlaskClient, conn: connection, use_report: str, service: str
):
    health_user = conftest.health_users[1 if service == "fitbit" else 5]
    form = health.WhoIsForm()
    form.name.data = health_user.gargling_id
    form.report.data = use_report
    response = client.post(
        f"/whoisyou/{service}/{health_user.service_user_id}", data=form.data
    )
    assert response.status_code == 200
    slack_nick, first_name = next(
        (user.slack_nick, user.first_name)
        for user in conftest.users
        if user.id == health_user.gargling_id
    )
    tokens = health.queries.tokens(conn, slack_nicks=[slack_nick], only_report=False)
    assert len(tokens) == 1
    assert tokens[0]["first_name"] == first_name
    daily_tokens = health.queries.tokens(conn, only_report=True, slack_nicks=None)
    amount = {"no": 0, "yes": 1}[use_report]
    assert (
        sum(token["id"] == str(health_user.service_user_id) for token in daily_tokens)
        == amount
    )
    assert response.data == b"Fumbs up!"


def test_who_is_you_reask(client: testing.FlaskClient, conn: connection):
    user = conftest.health_users[2]
    print(user)
    form = health.WhoIsForm()
    form.name.data = ""
    response = client.post(
        f"/whoisyou/fitbit/{user.service_user_id}",
        data=form.data,
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert response.data != b"Fumbs up!"
    assert b"<form " in response.data


@patch.object(health, "WithingsApi")
@patch.object(health, "FitbitApi")
def test_daily_report(mock_Fitbit: Mock, mock_Withings: Mock, conn: connection):
    test_date = pendulum.datetime(2020, 1, 2, 12)
    pendulum.set_test_now(test_date)
    withings_instance1, withings_instance2 = Mock(), Mock()
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
                date=arrow.get(test_date.subtract(days=1)), steps=6620, **none_data
            ),
        ),
        more=False,
        offset=0,
    )
    withings_instance2.measure_get_activity.return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(
                date=arrow.get(test_date.subtract(days=1)), steps=6619, **none_data
            ),
            MeasureGetActivityActivity(
                date=arrow.get(test_date), steps=22, **none_data
            ),
        ),
        more=False,
        offset=0,
    )
    mock_Withings.side_effect = [withings_instance1, withings_instance2]

    fitbit_instance1, fitbit_instance2 = Mock(), Mock()
    mock_Fitbit.side_effect = [fitbit_instance1, fitbit_instance2]
    fitbit_instance1.get_bodyweight.return_value = {
        "weight": [{"date": "2000-01-02", "time": "10:11:12", "weight": 50}]
    }
    fitbit_instance2.get_bodyweight.return_value = {
        "weight": [
            {"date": "2020-01-01", "time": "10:11:12", "weight": 75},
            {"date": "2020-01-02", "time": "10:11:12", "weight": 100},
        ]
    }
    fitbit_instance1.time_series.return_value = {
        "activities-steps": [{"dateTime": "2020-01-01", "value": "13475"}]
    }
    fitbit_instance2.time_series.return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13474"},
            {"dateTime": "2020-01-02", "value": "86"},
        ]
    }
    response = health.report(conn)
    assert response is not None

    assert len(response["blocks"]) == 4

    assert any("*6620* skritt" in block["text"]["text"] for block in response["blocks"])
    assert any("*6619* skritt" in block["text"]["text"] for block in response["blocks"])
    assert not any(
        "*22* skritt" in block["text"]["text"] for block in response["blocks"]
    )

    assert any(
        "*13475* skritt" in block["text"]["text"] for block in response["blocks"]
    )
    assert any(
        "*13474* skritt" in block["text"]["text"] for block in response["blocks"]
    )
    assert not any(
        "*86* skritt" in block["text"]["text"] for block in response["blocks"]
    )

    assert any("*100* kg" in block["text"]["text"] for block in response["blocks"])
    assert not any("*50* kg" in block["text"]["text"] for block in response["blocks"])
    assert not any("*125* kg" in block["text"]["text"] for block in response["blocks"])


@patch.object(health, "WithingsApi")
@patch.object(health, "FitbitApi")
def test_daily_report_no_data(mock_Fitbit: Mock, mock_Withings: Mock, conn: connection):
    withings_instance1, withings_instance2 = Mock(), Mock()
    mock_Withings.side_effect = [withings_instance1, withings_instance2]
    withings_instance1.measure_get_activity.return_value = MeasureGetActivityResponse(
        activities=[], more=False, offset=0
    )
    withings_instance2.measure_get_activity.return_value = MeasureGetActivityResponse(
        activities=[], more=False, offset=0
    )

    fitbit_instance1, fitbit_instance2 = Mock(), Mock()
    mock_Fitbit.side_effect = [fitbit_instance1, fitbit_instance2]
    fitbit_instance1.get_bodyweight.return_value = {"weight": []}
    fitbit_instance2.get_bodyweight.return_value = {"weight": []}
    fitbit_instance1.time_series.return_value = {"activities-steps": []}
    fitbit_instance2.time_series.return_value = {"activities-steps": []}

    response = health.report(conn)
    assert response is None
