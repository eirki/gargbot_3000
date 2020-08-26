#! /usr/bin/env python3
# coding: utf-8
from operator import itemgetter
import typing as t

from fitbit import Fitbit as FitbitApi
from fitbit.api import FitbitOauth2Client
import pendulum
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.health.base import (
    HealthService,
    HealthUser,
    connection_context,
    queries,
)


class FitbitService(HealthService):
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

    def token(self, code: str) -> t.Tuple[str, dict]:
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
                service="fitbit",
            )
            conn.commit()


class FitbitUser(HealthUser):
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
        super().__init__(gargling_id, first_name)
        self.client = FitbitApi(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_cb=self.service.persist_token,
            system=FitbitApi.METRIC,
        )

    def _steps_api_call(self, date: pendulum.Date) -> dict:
        return self.client.time_series(
            resource="activities/steps", base_date=date, period="1d"
        )

    def steps(self, date: pendulum.Date, conn: None = None) -> t.Optional[int]:
        data = self._steps_api_call(date)
        if not data["activities-steps"]:
            return None
        entry = data["activities-steps"][0]
        return int(entry["value"]) if entry else None

    def _weight_api_call(self, date: pendulum.Date) -> dict:
        return self.client.get_bodyweight(base_date=date, period="1w")

    def _bodyfat_api_call(self, date: pendulum.Date) -> dict:
        return self.client.get_bodyfat(base_date=date, period="1w")

    def body(self, date: pendulum.Date) -> dict:
        def most_recent(entries: t.List[dict]) -> t.Optional[dict]:
            if len(entries) == 0:
                return None
            for entry in entries:
                entry["datetime"] = pendulum.parse(
                    f"{entry['date']}T{entry['time']}"
                ).date()
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
                print(elapsed)
        fat_data = self._bodyfat_api_call(date)
        fat_entry = most_recent(fat_data["fat"])
        if fat_entry is not None and fat_entry["datetime"] == date:
            fat = fat_entry["fat"]

        return {
            "weight": weight,
            "elapsed": elapsed,
            "fat": fat,
        }
