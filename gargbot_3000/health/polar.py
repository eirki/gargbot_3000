#! /usr/bin/env python3.6
# coding: utf-8
from collections import defaultdict
from operator import itemgetter
import typing as t

from accesslink import AccessLink as PolarApi
from accesslink.endpoints.daily_activity_transaction import DailyActivityTransaction
import pendulum
from psycopg2.extensions import connection
import requests

from gargbot_3000 import config
from gargbot_3000.health.base import (
    HealthService,
    HealthUser,
    connection_context,
    queries,
)
from gargbot_3000.logger import log


class PolarService(HealthService):
    name = "polar"

    def __init__(self):
        client = PolarApi(
            client_id=config.polar_client_id,
            client_secret=config.polar_client_secret,
            redirect_url=config.polar_redirect_uri,
        )
        self.client: PolarApi = client

    def authorization_url(self) -> str:
        auth_url = self.client.get_authorization_url()
        return auth_url

    def token(self, code: str) -> t.Tuple[int, dict]:
        token = self.client.get_access_token(code)
        try:
            self.client.users.register(access_token=token["access_token"])
        except requests.exceptions.HTTPError as e:
            # Error 409 Conflict means that the user has already been registered for this client.
            if e.response.status_code != 409:
                raise e
        return token["x_user_id"], token

    @staticmethod
    def persist_token(token: dict, conn: t.Optional[connection] = None) -> None:
        with connection_context(conn) as conn:
            queries.persist_token(
                conn,
                id=token["x_user_id"],
                access_token=token["access_token"],
                refresh_token=None,
                expires_at=None,
                service="polar",
            )
            conn.commit()


class PolarUser(HealthUser):
    service = PolarService

    def __init__(
        self,
        gargling_id: int,
        first_name: str,
        service_user_id: str,
        access_token: str,
        refresh_token: None,
        expires_at: None,
    ):
        super().__init__(gargling_id, first_name)
        self.client = PolarApi(
            client_id=config.polar_client_id, client_secret=config.polar_client_secret
        )
        self.user_id = service_user_id
        self.token = access_token

    def _get_transaction(self) -> t.Optional[DailyActivityTransaction]:
        trans = self.client.daily_activity.create_transaction(self.user_id, self.token)
        return trans

    def steps(self, date: pendulum.Date, conn: connection = None) -> t.Optional[int]:
        log.info("Getting polar steps")
        if conn is None:
            raise Exception("No database connection available")
        trans = self._get_transaction()
        if trans is not None:
            activities = trans.list_activities()["activity-log"]
            log.info(f"number of activities: {len(activities)}")
            steps_by_date: t.Dict[pendulum.Date, list] = defaultdict(list)
            for activity in activities:
                summary = trans.get_activity_summary(activity)
                log.info(summary)
                created_at = pendulum.parse(summary["created"])
                n_steps = summary["active-steps"]
                log.info(f"n steps {created_at}: {n_steps}")
                steps_by_date[created_at.date()].append(
                    {"n_steps": n_steps, "created_at": created_at}
                )

            not_past: t.List[dict] = []
            for activity_date, activity_list in steps_by_date.items():
                activity_list.sort(key=itemgetter("created_at"))
                last_synced = activity_list[-1]
                if last_synced["created_at"].date() < date:
                    continue
                last_synced["gargling_id"] = self.gargling_id
                log.info(f"last_synced, {activity_date}: {last_synced}")
                not_past.append(last_synced)
            queries.upsert_steps(conn, not_past)
            conn.commit()
            trans.commit()
        todays_data = queries.cached_step_for_date(conn, date=date, id=self.gargling_id)
        steps = todays_data["n_steps"] if todays_data is not None else 0
        return steps

    def body(self, date: pendulum.Date) -> None:
        return None
