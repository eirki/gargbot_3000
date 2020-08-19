#! /usr/bin/env python3.6
# coding: utf-8
from abc import ABCMeta, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from operator import itemgetter
import typing as t

from accesslink import AccessLink as PolarApi
from accesslink.endpoints.daily_activity_transaction import DailyActivityTransaction
import aiosql
from fitbit import Fitbit as FitbitApi
from fitbit.api import FitbitOauth2Client
from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum
from psycopg2.extensions import connection
import requests
import withings_api
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import Credentials, GetActivityField

from gargbot_3000 import config
from gargbot_3000 import database as db
from gargbot_3000.logger import log

queries = aiosql.from_path("sql/health.sql", driver_adapter=db.JinjaSqlAdapter)
blueprint = Blueprint("health", __name__)
withings_api.common.enforce_type = lambda value, expected: value


@contextmanager
def connection_context(
    conn=t.Optional[connection],
) -> t.Generator[connection, None, None]:
    if conn is not None:
        yield conn
    elif current_app:
        with current_app.pool.get_connection() as conn:
            yield conn
    else:
        conn = db.connect()
        try:
            yield conn
        finally:
            conn.close()


token_type = t.Union[Credentials, dict]
service_user_id_type = t.Union[int, str]


class HealthService(metaclass=ABCMeta):
    name: str
    client: t.Union[WithingsAuth, FitbitOauth2Client, PolarApi]

    @classmethod
    def init(cls, service_name: str) -> "HealthService":
        services: t.Dict[str, t.Type["HealthService"]] = {
            "withings": Withings,
            "fitbit": Fitbit,
            "polar": Polar,
        }
        service = services[service_name]()
        return service

    @abstractmethod
    def authorization_url(cls) -> str:
        pass

    @abstractmethod
    def token(cls, code: str) -> t.Tuple[service_user_id_type, token_type]:
        pass

    @staticmethod
    @abstractmethod
    def persist_token(token, conn) -> None:
        pass


class Withings(HealthService):
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
                service="withings",
            )
            conn.commit()


class Fitbit(HealthService):
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


class Polar(HealthService):
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


@blueprint.route("/<service_name>/auth", methods=["GET"])
@jwt_required
def authorize(service_name: str):
    gargling_id = get_jwt_identity()
    if gargling_id is None:
        raise Exception("JWT token issued to None")
    log.info(f"gargling_id: {gargling_id}")
    with current_app.pool.get_connection() as conn:
        data = queries.is_registered(
            conn, gargling_id=gargling_id, service=service_name
        )
    if data is None:
        log.info("not registered")
        service = HealthService.init(service_name)
        url = service.authorization_url()
        log.info(url)
        response = jsonify(auth_url=url)
    else:
        report_enabled = data["enable_report"]
        log.info(f"registered, report enabled: {report_enabled}")
        response = jsonify(report_enabled=report_enabled)
    log.info(response)
    return response


@blueprint.route("/<service_name>/redirect", methods=["GET"])
@jwt_required
def handle_redirect(service_name: str):
    gargling_id = get_jwt_identity()
    if gargling_id is None:
        raise Exception("JWT token issued to None")
    log.info(f"gargling_id: {gargling_id}")
    log.info(request)
    code = request.args["code"]
    service = HealthService.init(service_name)
    service_user_id, token = service.token(code)
    with current_app.pool.get_connection() as conn:
        service.persist_token(token, conn)
        queries.match_ids(
            conn,
            gargling_id=gargling_id,
            service_user_id=service_user_id,
            service=service.name,
        )
        conn.commit()
    return Response(status=200)


@blueprint.route("/toggle_report", methods=["POST"])
@jwt_required
def toggle_report():
    gargling_id = get_jwt_identity()
    content = request.json
    service = HealthService.init(content["service"])
    enable = content["enable"]
    with current_app.pool.get_connection() as conn:
        queries.toggle_report(
            conn, enable_=enable, gargling_id=gargling_id, service=service.name
        )
        conn.commit()
    return Response(status=200)


class HealthUser(metaclass=ABCMeta):
    service: t.ClassVar[t.Type[HealthService]]
    first_name: str
    gargling_id: int

    @abstractmethod
    def __init__(self, token):
        pass

    @classmethod
    def init(cls, token: dict) -> "HealthUser":
        services: t.Dict[str, t.Type["HealthUser"]] = {
            "withings": WithingsUser,
            "fitbit": FitbitUser,
            "polar": PolarUser,
        }
        Service = services[token["service"]]
        service = Service(token)
        return service

    @abstractmethod
    def steps(
        self, date: pendulum.Date, conn: t.Optional[connection] = None
    ) -> t.Optional[int]:
        pass

    @abstractmethod
    def body(self, date: pendulum.Date) -> t.Optional[dict]:
        pass


class WithingsUser(HealthUser):
    service = Withings

    def __init__(self, token):
        credentials = Credentials(
            userid=token["id"],
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_expiry=token["expires_at"],
            client_id=config.withings_client_id,
            consumer_secret=config.withings_consumer_secret,
            token_type="Bearer",
        )
        self.client: WithingsApi = WithingsApi(
            credentials, refresh_cb=self.service.persist_token
        )
        self.first_name = token["first_name"]
        self.gargling_id = token["gargling_id"]

    def steps(self, date: pendulum.Date, conn: None = None) -> t.Optional[int]:
        result = self.client.measure_get_activity(
            data_fields=[GetActivityField.STEPS],
            startdateymd=date,
            enddateymd=date.add(days=1),
        )
        entry = next(
            (act for act in result.activities if act.date.day == date.day), None,
        )
        return entry.steps if entry else None

    def body(self, date: pendulum.Date) -> None:
        return None


class FitbitUser(HealthUser):
    service = Fitbit

    def __init__(self, token):
        client = FitbitApi(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            expires_at=token["expires_at"],
            refresh_cb=self.service.persist_token,
            system=FitbitApi.METRIC,
        )
        self.client: FitbitApi = client
        self.first_name = token["first_name"]
        self.gargling_id = token["gargling_id"]

    def steps(self, date: pendulum.Date, conn: None = None) -> t.Optional[int]:
        data = self.client.time_series(
            resource="activities/steps", base_date=date, period="1d"
        )
        if not data["activities-steps"]:
            return None
        entry = data["activities-steps"][0]
        return int(entry["value"]) if entry else None

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
        weight_data = self.client.get_bodyweight(base_date=date, period="1w")
        weight_entry = most_recent(weight_data["weight"])
        if weight_entry is not None:
            if weight_entry["datetime"] == date:
                weight = weight_entry["weight"]
            else:
                elapsed = (date - weight_entry["datetime"]).days
                print(elapsed)
        fat_data = self.client.get_bodyfat(base_date=date, period="1w")
        fat_entry = most_recent(fat_data["fat"])
        if fat_entry is not None and fat_entry["datetime"] == date:
            fat = fat_entry["fat"]

        return {
            "weight": weight,
            "elapsed": elapsed,
            "fat": fat,
        }


class PolarUser(HealthUser):
    service = Polar

    def __init__(self, token):
        self.client = PolarApi(
            client_id=config.polar_client_id, client_secret=config.polar_client_secret
        )
        self.first_name = token["first_name"]
        self.gargling_id = token["gargling_id"]
        self.user_id = token["id"]
        self.token = token["access_token"]

    def _get_transaction(self) -> DailyActivityTransaction:
        trans = self.client.daily_activity.create_transaction(self.user_id, self.token)
        return trans

    def steps(self, date: pendulum.Date, conn: connection = None) -> t.Optional[int]:
        if conn is None:
            raise Exception("No database connection available")
        trans = self._get_transaction()
        activities = trans.list_activities()
        steps_by_date: t.Dict[pendulum.Date, int] = defaultdict(int)
        for activity in activities["activity-log"]:
            summary = trans.get_activity_summary(activity)
            steps_by_date[pendulum.parse(summary["date"]).date()] += summary[
                "active-steps"
            ]
        not_past = [
            {"taken_at": sdate, "n_steps": steps, "gargling_id": self.gargling_id}
            for sdate, steps in steps_by_date.items()
            if sdate >= date
        ]
        queries.upsert_steps(conn, not_past)
        conn.commit()
        trans.commit()
        todays_data = queries.cached_step_for_date(conn, date=date, id=self.gargling_id)
        steps = todays_data["n_steps"] if todays_data is not None else 0
        return steps

    def body(self, date: pendulum.Date) -> None:
        return None


def steps(
    conn: connection, users: t.List[HealthUser], date: pendulum.Date
) -> t.List[dict]:
    step_amounts = []
    for user in users:
        try:
            steps = (
                user.steps(date)
                if user.service.name != "polar"
                else user.steps(date, conn)
            )
        except Exception:
            log.error(
                f"Error getting {user.service.name} steps data for {user.first_name}",
                exc_info=True,
            )
            continue
        if steps is None:
            continue
        step_amounts.append({"amount": steps, "gargling_id": user.gargling_id})
    return step_amounts


def get_body_data(users: t.List[HealthUser], date: pendulum.Date) -> t.List[dict]:
    all_data = []
    for user in users:
        try:
            body_data = user.body(date)
        except Exception:
            log.error(
                f"Error getting {user.service.name} body data for {user.first_name}",
                exc_info=True,
            )
        else:
            if body_data is None:
                continue
            body_data["first_name"] = user.first_name
            all_data.append(body_data)
    return all_data


def body_details(body_data: t.List[dict]) -> t.Optional[list]:
    user_reports = []
    for datum in body_data:
        weight = datum["weight"]
        fat = datum["fat"]
        # elapsed = datum["elapsed"]
        name = datum["first_name"]
        user_report = None
        if weight is not None:
            user_report = f"{name} veier *{weight}* kg. "
            if fat is not None:
                user_report += f"Body fat percentage er *{fat}*"
        elif fat is not None:
            user_report = f"{name} sin body fat percentage er *{fat}*. "
        # elif elapsed is not None:
        #     user_report = f"{name} har ikke veid seg på *{elapsed}* dager. Skjerpings! "
        if user_report is not None:
            user_reports.append(user_report)
    return user_reports


def activity(
    conn: connection, date: pendulum.Date
) -> t.Optional[t.Tuple[list, t.Optional[list]]]:
    tokens = queries.tokens(conn)
    if not tokens:
        return None
    users = [HealthUser.init(token) for token in tokens]
    steps_data = steps(conn, users, date)
    body_data = get_body_data(users, date)
    body_reports = body_details(body_data)
    return steps_data, body_reports
