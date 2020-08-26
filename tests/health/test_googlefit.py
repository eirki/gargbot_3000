#! /usr/bin/env python3
# coding: utf-8
from unittest.mock import patch

from flask import testing
from google.oauth2.credentials import Credentials
import pendulum
from psycopg2.extensions import connection

from gargbot_3000 import config
from tests import conftest


@patch("gargbot_3000.health.get_jwt_identity")
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


@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_auth_is_registered(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient
):
    user = conftest.health_users[1]
    mock_jwt_identity.return_value = user.gargling_id
    response = client.get("googlefit/auth")
    assert response.status_code == 200
    assert "report_enabled" in response.json


@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_handle_redirect_reregister(
    mock_jwt_required, mock_jwt_identity, client: testing.FlaskClient, conn: connection,
):
    user = conftest.health_users[1]
    fake_token = Credentials(
        token=user.access_token,
        refresh_token=user.refresh_token,
        client_id=config.googlefit_client_id,
        client_secret=config.googlefit_client_secret,
        token_uri="token_uri",
    )
    fake_token.expiry = pendulum.datetime(2013, 3, 31, 0, 0, 0)
    mock_jwt_identity.return_value = user.gargling_id
    with patch("gargbot_3000.health.googlefit.GooglefitService.token") as mock_handler:
        mock_handler.return_value = None, fake_token
        response = client.get("/googlefit/redirect", query_string={"code": "123"})
    assert response.status_code == 200
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM googlefit_token where id = %(fake_user_id)s",
            {"fake_user_id": user.service_user_id},
        )
        data = cursor.fetchone()
    assert data["access_token"] == fake_token.token
    assert data["refresh_token"] == fake_token.refresh_token
    assert pendulum.from_timestamp((data["expires_at"])) == fake_token.expiry
    assert data["token_uri"] == fake_token.token_uri
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT gargling_id "
            f"FROM googlefit_token_gargling where googlefit_id = %(fake_user_id)s",
            {"fake_user_id": user.service_user_id},
        )
        data = cursor.fetchone()
    assert data["gargling_id"] == user.gargling_id
