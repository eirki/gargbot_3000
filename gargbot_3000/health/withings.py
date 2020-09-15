#! /usr/bin/env python3
# coding: utf-8
import typing as t

import pendulum
from psycopg2.extensions import connection
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import (
    Credentials,
    GetActivityField,
    MeasureGetActivityResponse,
)

from gargbot_3000 import config
from gargbot_3000.health.common import connection_context, queries


class WithingsService:
    name = "withings"

    def __init__(self):
        scope = (
            AuthScope.USER_ACTIVITY,
            AuthScope.USER_METRICS,
            AuthScope.USER_INFO,
            AuthScope.USER_SLEEP_EVENTS,
        )
        client = WithingsAuth(
            client_id=config.withings_client_id,
            consumer_secret=config.withings_consumer_secret,
            callback_uri=config.withings_redirect_uri,
            scope=scope,
        )
        self.client: WithingsAuth = client

    def authorization_url(self) -> str:
        url = self.client.get_authorize_url()
        return url

    def token(self, code: str) -> t.Tuple[int, Credentials]:
        credentials = self.client.get_credentials(code)
        return credentials.userid, credentials

    @staticmethod
    def persist_token(
        credentials: Credentials, conn: t.Optional[connection] = None
    ) -> None:
        with connection_context(conn) as conn:
            queries.persist_token(
                conn,
                id=credentials.userid,
                access_token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                expires_at=credentials.token_expiry,
                token_table="withings_token",
            )
            conn.commit()


class WithingsUser:
    service = WithingsService

    def __init__(
        self,
        gargling_id: int,
        first_name: str,
        service_user_id: str,
        access_token: str,
        refresh_token: str,
        expires_at: int,
    ):
        self.gargling_id = gargling_id
        self.first_name = first_name
        credentials = Credentials(
            userid=service_user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expiry=expires_at,
            client_id=config.withings_client_id,
            consumer_secret=config.withings_consumer_secret,
            token_type="Bearer",
        )
        self.client: WithingsApi = WithingsApi(
            credentials, refresh_cb=self.service.persist_token
        )

    def _steps_api_call(self, date: pendulum.Date) -> MeasureGetActivityResponse:
        return self.client.measure_get_activity(
            data_fields=[GetActivityField.STEPS],
            startdateymd=date,
            enddateymd=date.add(days=1),
        )

    def steps(self, date: pendulum.Date) -> t.Optional[int]:
        result = self._steps_api_call(date)
        entry = next(
            (act for act in result.activities if act.date.day == date.day), None,
        )
        return entry.steps if entry else 0

    def body(self, date: pendulum.Date) -> None:
        return None
