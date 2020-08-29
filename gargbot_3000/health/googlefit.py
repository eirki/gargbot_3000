#! /usr/bin/env python3
# coding: utf-8
import typing as t

import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import pendulum
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.health.base import (
    HealthService,
    HealthUser,
    connection_context,
    queries,
)
from gargbot_3000.logger import log

scopes = ["https://www.googleapis.com/auth/fitness.activity.read"]


class GooglefitService(HealthService):
    name = "googlefit"

    def __init__(self):
        client_config = {
            "web": {
                "client_id": config.googlefit_client_id,
                "project_id": "scripts-140708",
                "auth_uri": config.googlefit_auth_uri,
                "token_uri": config.googlefit_token_uri,
                "auth_provider_x509_cert_url": config.googlefit_auth_provider_x509_cert_url,
                "client_secret": config.googlefit_client_secret,
                "redirect_uris": [config.googlefit_redirect_uri],
                "javascript_origins": [config.googlefit_javascript_origins],
            }
        }
        flow = Flow.from_client_config(client_config, scopes=scopes)
        flow.redirect_uri = config.googlefit_redirect_uri
        self.client = flow

    def authorization_url(self) -> str:
        authorization_url, state = self.client.authorization_url(
            access_type="offline", include_granted_scopes="true"
        )
        return authorization_url

    def token(self, code: str) -> t.Tuple[None, Credentials]:
        self.client.fetch_token(code=code)
        credentials = self.client.credentials
        return None, credentials

    @staticmethod
    def insert_token(
        credentials: Credentials,
        conn: t.Optional[connection] = None,
    ) -> int:
        with connection_context(conn) as conn:
            service_user_id = queries.insert_googlefit_token(
                conn,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=credentials.expiry.timestamp(),
            )
            conn.commit()
        return service_user_id

    @staticmethod
    def update_token(
        service_user_id: int,
        credentials: Credentials,
        conn: t.Optional[connection] = None,
    ) -> None:
        with connection_context(conn) as conn:
            queries.update_googlefit_token(
                conn,
                id=service_user_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=credentials.expiry.timestamp(),
            )
            conn.commit()


class GooglefitUser(HealthUser):
    service = GooglefitService

    def __init__(
        self,
        gargling_id: int,
        first_name: str,
        service_user_id: int,
        access_token: str,
        refresh_token: str,
        expires_at: float,
    ):
        super().__init__(gargling_id, first_name)
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            client_id=config.googlefit_client_id,
            client_secret=config.googlefit_client_secret,
            scopes=scopes,
            token_uri=config.googlefit_token_uri,
        )
        credentials.expiry = pendulum.from_timestamp(expires_at).naive()
        if credentials.expired:
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            self.service.update_token(service_user_id, credentials)
        if not credentials.valid:
            raise Exception("Invalid credentials")
        self.client = build(
            "fitness", "v1", credentials=credentials, cache_discovery=False
        )

    def _steps_api_call(self, start_ms: int, end_ms: int) -> dict:
        return (
            self.client.users()
            .dataset()
            .aggregate(
                userId="me",
                body={
                    "aggregateBy": [
                        {
                            "dataTypeName": "com.google.step_count.delta",
                            "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps",
                        }
                    ],
                    "bucketByTime": {
                        "durationMillis": pendulum.duration(days=1).in_seconds() * 1000
                    },
                    "startTimeMillis": start_ms,
                    "endTimeMillis": end_ms,
                },
            )
            .execute()
        )

    def steps(self, date: pendulum.Date, conn: None = None) -> t.Optional[int]:
        start_dt = pendulum.datetime(date.year, date.month, date.day).in_timezone(
            config.tz
        )
        start_ms = start_dt.timestamp() * 1000
        end_ms = start_dt.add(days=1).timestamp() * 1000
        data = self._steps_api_call(start_ms, end_ms)
        log.info(data)
        try:
            return data["bucket"][0]["dataset"][0]["point"][0]["value"][0]["intVal"]
        except IndexError:
            return None

    def body(self, date: pendulum.Date):
        pass
