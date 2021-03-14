#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from operator import itemgetter
import typing as t

import fitbit
from fitbit import Fitbit as FitbitApi
from fitbit.api import FitbitOauth2Client
import pendulum
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.health.common import connection_context, queries


class FitbitService:
    name = "fitbit"

    def __init__(self):
        client = FitbitOauth2Client(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            redirect_uri=config.fitbit_redirect_uri,
            timeout=10,
        )
        self.client: FitbitOauth2Client = client

    def authorization_url(self) -> str:
        scope = ["activity", "heartrate", "sleep", "weight"]
        url, _ = self.client.authorize_token_url(scope=scope)
        return url

    def token(self, code: str) -> tuple[str, dict]:  # no test coverage
        self.client.fetch_access_token(code)
        token = self.client.session.token
        return token["user_id"], token

    @staticmethod
    def persist_token(token: dict, conn: t.Optional[connection] = None) -> None:
        with connection_context(conn) as conn:
            queries.persist_token(
                conn,
                id=token["user_id"],
                access_token=token["access_token"],
                refresh_token=token["refresh_token"],
                expires_at=token["expires_at"],
                token_table="fitbit_token",
            )
            conn.commit()


class FitbitUser:
    service = FitbitService

    def __init__(
        self,
        gargling_id: int,
        first_name: str,
        access_token: str,
        refresh_token: str,
        expires_at: int,
        service_user_id: None,
    ):
        self.gargling_id = gargling_id
        self.first_name = first_name
        self.client = FitbitApi(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_cb=self.service.persist_token,
            system=FitbitApi.METRIC,
        )

    def _steps_api_call(self, date: pendulum.Date) -> dict:  # no test coverage
        kwargs = {"resource": "activities/steps", "base_date": date, "period": "1d"}
        try:
            return self.client.time_series(**kwargs)
        except fitbit.exceptions.HTTPServerError:
            # retry
            return self.client.time_series(**kwargs)

    def steps(self, date: pendulum.Date) -> t.Optional[int]:
        data = self._steps_api_call(date)
        if not data["activities-steps"]:
            return 0
        entry = data["activities-steps"][0]
        return int(entry["value"]) if entry else 0

    def _weight_api_call(self, date: pendulum.Date) -> dict:  # no test coverage
        return self.client.get_bodyweight(base_date=date, period="1w")

    def _bodyfat_api_call(self, date: pendulum.Date) -> dict:  # no test coverage
        return self.client.get_bodyfat(base_date=date, period="1w")

    def body(self, date: pendulum.Date) -> dict:
        def most_recent(entries: list[dict]) -> t.Optional[dict]:
            if len(entries) == 0:
                return None
            for entry in entries:
                parsed = pendulum.parse(f"{entry['date']}T{entry['time']}")
                assert isinstance(parsed, pendulum.DateTime)
                entry["datetime"] = parsed.date()
            entries.sort(key=itemgetter("datetime"), reverse=True)
            return entries[0]

        weight = None
        elapsed = None
        fat = None
        weight_data = self._weight_api_call(date)
        weight_entry = most_recent(weight_data["weight"])
        if weight_entry is not None:
            if weight_entry["datetime"] == date:
                weight = weight_entry["weight"]
            else:
                elapsed = (date - weight_entry["datetime"]).days
        fat_data = self._bodyfat_api_call(date)
        fat_entry = most_recent(fat_data["fat"])
        if fat_entry is not None and fat_entry["datetime"] == date:
            fat = fat_entry["fat"]

        return {
            "weight": weight,
            "elapsed": elapsed,
            "fat": fat,
        }
