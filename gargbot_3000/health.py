#! /usr/bin/env python3.6
# coding: utf-8
from contextlib import contextmanager
import datetime as dt
import enum
from operator import attrgetter, itemgetter
import typing as t

import aiosql
from fitbit import Fitbit as FitbitApi
from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum
from psycopg2.extensions import connection
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


class Withings:
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

    @staticmethod
    def auth_client():
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
        return client

    @staticmethod
    def authorize_user():
        auth_client = Withings.auth_client()
        url = auth_client.get_authorize_url()
        return url

    @staticmethod
    def handle_redirect(request):
        code = request.args["code"]
        auth_client = Withings.auth_client()
        credentials = auth_client.get_credentials(code)
        return credentials.userid, credentials

    @staticmethod
    def init_client(token: dict,) -> WithingsApi:
        credentials = Credentials(
            userid=token["id"],
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            token_expiry=token["expires_at"],
            client_id=config.withings_client_id,
            consumer_secret=config.withings_consumer_secret,
            token_type="Bearer",
        )
        client = WithingsApi(credentials, refresh_cb=Withings.persist_token)
        return client

    @staticmethod
    def weight(client: WithingsApi, date: pendulum.DateTime) -> t.Optional[dict]:
        return None
        data = client.measure_get_meas(
            startdate=date, enddate=date.add(days=1), meastype=MeasureType.WEIGHT,
        ).measuregrps
        if not data:
            log.info("No weight data")
            return None
        data = sorted(data, key=attrgetter("date"), reverse=True)
        most_recent = data[0]
        measure = most_recent.measures[0]
        return {
            "weight": float(measure.value * pow(10, measure.unit)),
            "datetime": most_recent.date,
        }

    @staticmethod
    def steps(client: WithingsApi, date: pendulum.DateTime) -> t.Optional[int]:
        result = client.measure_get_activity(
            data_fields=[GetActivityField.STEPS],
            startdateymd=date,
            enddateymd=date.add(days=1),
        )
        entry = next(
            (act for act in result.activities if act.date.day == date.day), None,
        )
        return entry.steps if entry else None

    @staticmethod
    def sleep(client: WithingsApi) -> str:
        return client.sleep_get_summary(
            data_fields=[
                GetSleepSummaryField.REM_SLEEP_DURATION,
                GetSleepSummaryField.LIGHT_SLEEP_DURATION,
                GetSleepSummaryField.DEEP_SLEEP_DURATION,
            ],
            startdateymd=pendulum.yesterday(),
            enddateymd=pendulum.today(),
        )


class Fitbit:
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

    @staticmethod
    def auth_client():
        api = FitbitApi(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            redirect_uri=config.fitbit_redirect_uri,
            timeout=10,
        )
        return api.client

    @staticmethod
    def authorize_user():
        scope = ["activity", "heartrate", "sleep", "weight"]
        auth_client = Fitbit.auth_client()
        url, _ = auth_client.authorize_token_url(scope=scope)
        return url

    @staticmethod
    def handle_redirect(request):
        code = request.args["code"]
        auth_client = Fitbit.auth_client()
        auth_client.fetch_access_token(code)
        token = auth_client.session.token
        return token["user_id"], token

    @staticmethod
    def init_client(token: dict) -> FitbitApi:
        client = FitbitApi(
            config.fitbit_client_id,
            config.fitbit_client_secret,
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            expires_at=token["expires_at"],
            refresh_cb=Fitbit.persist_token,
            system=FitbitApi.METRIC,
        )
        return client

    @staticmethod
    def weight(client: FitbitApi, date: pendulum.DateTime) -> t.Optional[dict]:
        data = client.get_bodyweight(base_date=date.subtract(days=6), period="1w")
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

    @staticmethod
    def steps(client: FitbitApi, date: pendulum.DateTime) -> t.Optional[int]:
        data = client.time_series(
            resource="activities/steps", base_date=date, period="1d"
        )
        if not data["activities-steps"]:
            return None
        entry = data["activities-steps"][0]
        return int(entry["value"]) if entry else None

    @staticmethod
    def sleep(client: FitbitApi) -> str:
        data = client.get_sleep(date=dt.datetime.today())
        log.info(f"sleep data: {data}")
        return data


class Service(enum.Enum):
    withings = Withings
    fitbit = Fitbit


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
        url = Service[service_name].value.authorize_user()
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
    service = Service[service_name]
    service_user_id, token = service.value.handle_redirect(request)
    with current_app.pool.get_connection() as conn:
        service.value.persist_token(token, conn)
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
    service = Service[content["service"]]
    enable = content["enable"]
    with current_app.pool.get_connection() as conn:
        queries.toggle_report(
            conn, enable_=enable, gargling_id=gargling_id, service=service.name
        )
        conn.commit()
    return Response(status=200)


def weight(clients, date: pendulum.DateTime) -> t.List[str]:
    reports = []
    for name, (client, service) in clients.items():
        try:
            weight_data = service.value.weight(client, date)
        except Exception:
            log.error(f"Error getting {service} weight data for {name}", exc_info=True)
            continue
        if weight_data is None:
            continue
        elapsed = (date - weight_data["datetime"]).days
        if elapsed < 2:
            desc = f"{name} veier nå *{weight_data['weight']}* kg!"
        else:
            desc = f"{name} har ikke veid seg på *{elapsed}* dager. Skjerpings!"
        reports.append(desc)
    return reports


def steps(clients, date: pendulum.DateTime) -> t.List[dict]:
    step_amounts = []
    for name, (client, service) in clients.items():
        try:
            steps = service.value.steps(client, date)
        except Exception:
            log.error(f"Error getting {service} steps data for {name}", exc_info=True)
            continue
        if steps is None:
            continue
        step_amounts.append({"amount": steps, "first_name": name})
    return step_amounts


def activity(
    conn: connection, date: pendulum.DateTime
) -> t.Optional[t.Tuple[list, list]]:
    tokens = queries.tokens(conn)
    if not tokens:
        return None
    clients = {}
    for token in tokens:
        service = Service[token["service"]]
        client = service.value.init_client(token)
        clients[token["first_name"]] = (client, service)
    steps_data = steps(clients, date)
    weight_data = weight(clients, date)
    return steps_data, weight_data
