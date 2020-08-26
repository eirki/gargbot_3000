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

scopes = ["https://www.googleapis.com/auth/fitness.activity.read"]


class GooglefitService(HealthService):
    name = "googlefit"

    def __init__(self):
        client_config = {
            "web": {
                "client_id": config.googlefit_client_id,
                "project_id": "scripts-140708",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
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
        credentials: Credentials, conn: t.Optional[connection] = None,
    ) -> int:
        with connection_context(conn) as conn:
            service_user_id = queries.insert_googlefit_token(
                conn,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
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
                token_uri=credentials.token_uri,
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
        )
        credentials.expiry = pendulum.from_timestamp(expires_at)
        if not credentials.valid:
            raise Exception("Invalid credentials")
        if credentials.expired:
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            self.service.update_token(service_user_id, credentials)
        self.client = build(
            "fitness", "v1", credentials=credentials, cache_discovery=False
        )

    def steps(self, date: pendulum.Date, conn: None = None) -> t.Optional[int]:
        steps_datasource = (
            "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
        )
        ONE_DAY_MS = 86400000
        start_dt = pendulum.DateTime(date.year, date.month, date.day).in_timezone(
            config.tz
        )
        start_ms = int(start_dt.format("x"))
        end_ms = start_ms + ONE_DAY_MS
        data = (
            self.client.users()
            .dataset()
            .aggregate(
                userId="me",
                body={
                    "aggregateBy": [
                        {
                            "dataTypeName": "com.google.step_count.delta",
                            "dataSourceId": steps_datasource,
                        }
                    ],
                    "bucketByTime": {"durationMillis": ONE_DAY_MS},
                    "startTimeMillis": start_ms,
                    "endTimeMillis": end_ms,
                },
            )
            .execute()
        )
        try:
            return data["bucket"][0]["dataset"][0]["point"]
        except IndexError:
            return None
        # for bucket in data["bucket"]:
        #     for dataset in bucket["dataset"]:
        #         for point in dataset["point"]:
        #             val = point["intVal"]
        # {
        #     "bucket": [
        #         {
        #             "startTimeMillis": "1598220000000",
        #             "endTimeMillis": "1598306400000",
        #             "dataset": [
        #                 {
        #                     "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:aggregated",
        #                     "point": [],
        #                 }
        #             ],
        #         }
        #     ]
        # }

    def body(self, date: pendulum.Date):
        pass
