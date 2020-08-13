#! /usr/bin/env python3.6
# coding: utf-8
from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
import datetime as dt
import enum
from operator import attrgetter, itemgetter
import typing as t

import accesslink as polar
import aiosql
from fitbit import Fitbit as FitbitApi
from fitbit.api import FitbitOauth2Client
from flask import Blueprint, Request, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum
from psycopg2.extensions import connection
import requests
import withings_api
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import (
    Credentials,
    GetActivityField,
    GetSleepSummaryField,
    MeasureType,
)

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
    client: t.Union[WithingsAuth, FitbitOauth2Client, polar.AccessLink]

    @classmethod
    def init(cls, service_name: str) -> "HealthService":
        services: t.Dict[str, t.Type["HealthService"]] = {
            "withings": Withings,
            "fitbit": Fitbit,
            "polar": Polar,
        }
        Service = services[service_name]()
        return Service

    @abstractmethod
    def authorize_user(cls) -> str:
        pass

    @abstractmethod
    def handle_redirect(cls, req: Request) -> t.Tuple[service_user_id_type, token_type]:
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

    def authorize_user(self) -> str:
        url = self.client.get_authorize_url()
        return url

    def handle_redirect(self, req: Request) -> t.Tuple[int, Credentials]:
        code = req.args["code"]
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

    def authorize_user(self) -> str:
        scope = ["activity", "heartrate", "sleep", "weight"]
        url, _ = self.client.authorize_token_url(scope=scope)
        return url

    def handle_redirect(self, req: Request) -> t.Tuple[str, dict]:
        code = req.args["code"]
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
        client = polar.AccessLink(
            client_id=config.polar_client_id,
            client_secret=config.polar_client_secret,
            redirect_url=config.polar_redirect_uri,
        )
        self.client: polar.AccessLink = client

    def authorize_user(self) -> str:
        auth_url = self.client.get_authorization_url()
        return auth_url

    def handle_redirect(self, req: Request) -> t.Tuple[int, dict]:
        code = req.args["code"]
        token = self.client.get_access_token(code)
        user_id = token["x_user_id"]
        try:
            self.client.users.register(access_token=token)
        except requests.exceptions.HTTPError as e:
            # Error 409 Conflict means that the user has already been registered for this client.
            # For most applications, that error can be ignored.
            if e.response.status_code != 409:
                raise e

        return user_id, token

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
        url = HealthService.init(service_name).authorize_user()
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
    Service = HealthService.init(service_name)
    service_user_id, token = Service.handle_redirect(request)
    with current_app.pool.get_connection() as conn:
        Service.persist_token(token, conn)
        queries.match_ids(
            conn,
            gargling_id=gargling_id,
            service_user_id=service_user_id,
            service=Service.name,
        )
        conn.commit()
    return Response(status=200)


@blueprint.route("/toggle_report", methods=["POST"])
@jwt_required
def toggle_report():
    gargling_id = get_jwt_identity()
    content = request.json
    Service = HealthService.init(content["service"])
    enable = content["enable"]
    with current_app.pool.get_connection() as conn:
        queries.toggle_report(
            conn, enable_=enable, gargling_id=gargling_id, service=Service.name
        )
        conn.commit()
    return Response(status=200)


class HealthUser(metaclass=ABCMeta):
    service: t.ClassVar[t.Type[HealthService]]
    first_name: str

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
    def steps(self, date: pendulum.DateTime) -> t.Optional[int]:
        pass

    @abstractmethod
    def weight(self, date: pendulum.DateTime) -> t.Optional[dict]:
        pass

    @abstractmethod
    def bodyfat(self, date: pendulum.DateTime) -> t.Optional[int]:
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

    def steps(self, date: pendulum.DateTime) -> t.Optional[int]:
        result = self.client.measure_get_activity(
            data_fields=[GetActivityField.STEPS],
            startdateymd=date,
            enddateymd=date.add(days=1),
        )
        entry = next(
            (act for act in result.activities if act.date.day == date.day), None,
        )
        return entry.steps if entry else None

    def weight(self, date: pendulum.DateTime) -> t.Optional[dict]:
        return None

    def bodyfat(self, date: pendulum.DateTime) -> None:
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

    def steps(self, date: pendulum.DateTime) -> t.Optional[int]:
        data = self.client.time_series(
            resource="activities/steps", base_date=date, period="1d"
        )
        if not data["activities-steps"]:
            return None
        entry = data["activities-steps"][0]
        return int(entry["value"]) if entry else None

    def weight(self, date: pendulum.DateTime) -> t.Optional[dict]:
        data = self.client.get_bodyweight(base_date=date, period="1w")
        if len(data["weight"]) == 0:
            log.info("No weight data")
            return None
        entries = data["weight"]
        for entry in entries:
            entry["datetime"] = pendulum.parse(f"{entry['date']}T{entry['time']}")
        entries.sort(key=itemgetter("datetime"), reverse=True)
        most_recent = entries[0]
        log.info(f"weight data: {most_recent}")
        return most_recent

    def bodyfat(self, date: pendulum.DateTime) -> t.Optional[int]:
        data = self.client.get_bodyfat(base_date=date, period="1w")
        if len(data["bodyfat"]) == 0:
            log.info("No bodyfat data")
            return None
        entries = data["bodyfat"]
        for entry in entries:
            entry["datetime"] = pendulum.parse(f"{entry['date']}T{entry['time']}")
        entries.sort(key=itemgetter("datetime"), reverse=True)
        most_recent = entries[0]
        if (date - most_recent["datetime"]).days > 2:
            log.info(f"No recent bodyfat data after {most_recent['datetime']}")
            return None
        log.info(f"bodyfat data: {most_recent}")
        return most_recent["fat"]


class PolarUser(HealthUser):
    service = Polar

    def __init__(self, token):
        self.client = polar.AccessLink(
            client_id=config.polar_client_id, client_secret=config.polar_client_secret
        )
        self.first_name = token["first_name"]
        self.user_id = token["id"]
        self.token = token["access_token"]

    def steps(self, date: pendulum.DateTime) -> t.Optional[int]:
        trans = self.client.daily_activity.create_transaction(self.user_id, self.token)
        log.info(trans)
        steps = trans.get_step_samples()
        log.info(steps)
        return None

    def weight(self, date: pendulum.DateTime) -> t.Optional[dict]:
        return None

    def bodyfat(self, date: pendulum.DateTime) -> t.Optional[int]:
        return None


def steps(users: t.List[HealthUser], date: pendulum.DateTime) -> t.List[dict]:
    step_amounts = []
    for user in users:
        try:
            steps = user.steps(date)
        except Exception:
            log.error(
                f"Error getting {user.service.name} steps data for {user.first_name}",
                exc_info=True,
            )
            continue
        if steps is None:
            continue
        step_amounts.append({"amount": steps, "first_name": user.first_name})
    return step_amounts


def body_details(users: t.List[HealthUser], date: pendulum.DateTime) -> t.List[str]:
    reports = []
    for user in users:
        desc = None
        try:
            weight_data = user.weight(date)
        except Exception:
            log.error(
                f"Error getting {user.service.name} weight data for {user.first_name}",
                exc_info=True,
            )
            weight_data = None
        try:
            bodyfat_data = user.bodyfat(date)
        except Exception:
            log.error(
                f"Error getting {user.service.name} bodyfat data for {user.first_name}",
                exc_info=True,
            )
            bodyfat_data = None

        if weight_data:
            elapsed = (date - weight_data["datetime"]).days
            if elapsed < 2:
                desc = f"{user.first_name} veier nå *{weight_data['weight']}* kg."
            else:
                desc = f"{user.first_name} har ikke veid seg på *{elapsed}* dager. Skjerpings!"
            if bodyfat_data:
                desc += f"Bodyfat prosent er {bodyfat_data}"
        elif bodyfat_data:
            desc = f"{user.first_name} sin bodyfat prosent er {bodyfat_data}"

        if desc:
            reports.append(desc)
    return reports


def activity(
    conn: connection, date: pendulum.DateTime
) -> t.Optional[t.Tuple[list, list]]:
    tokens = queries.tokens(conn)
    if not tokens:
        return None
    users = [HealthUser.init(token) for token in tokens]
    steps_data = steps(users, date)
    body_reports = body_details(users, date)
    return steps_data, body_reports
