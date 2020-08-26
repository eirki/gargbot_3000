#! /usr/bin/env python3
# coding: utf-8
import typing as t

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum
from psycopg2.extensions import connection
import withings_api

from gargbot_3000.health.base import HealthService, HealthUser, queries
from gargbot_3000.health.fitbit_ import FitbitService, FitbitUser
from gargbot_3000.health.googlefit import GooglefitService, GooglefitUser
from gargbot_3000.health.polar import PolarService, PolarUser
from gargbot_3000.health.withings import WithingsService, WithingsUser
from gargbot_3000.logger import log

withings_api.common.enforce_type = lambda value, expected: value

blueprint = Blueprint("health", __name__)


def init_service(service_name: str) -> HealthService:
    services: t.Dict[str, t.Type[HealthService]] = {
        "fitbit": FitbitService,
        "googlefit": GooglefitService,
        "polar": PolarService,
        "withings": WithingsService,
    }
    service = services[service_name]()
    return service


def init_user(token: dict) -> HealthUser:
    services: t.Dict[str, t.Type[HealthUser]] = {
        "fitbit": FitbitUser,
        "googlefit": GooglefitUser,
        "polar": PolarUser,
        "withings": WithingsUser,
    }
    User = services[token.pop("service")]
    user = User(**token)
    return user


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
        service = init_service(service_name)
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
    service = init_service(service_name)
    service_user_id, token = service.token(code)
    with current_app.pool.get_connection() as conn:
        if (
            isinstance(service, GooglefitService)
            and queries.is_registered(
                conn, gargling_id=gargling_id, service=GooglefitService.name
            )
            is not None
        ):

            service_user_id_ = queries.service_user_id_for_gargling_id(
                conn, gargling_id=gargling_id, service=GooglefitService.name
            )["service_user_id"]
            service.update_token(service_user_id_, token, conn)
        else:
            if isinstance(service, GooglefitService):
                service_user_id = service.insert_token(token, conn)
            else:
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
    service = init_service(content["service"])
    enable = content["enable"]
    with current_app.pool.get_connection() as conn:
        queries.toggle_report(
            conn, enable_=enable, gargling_id=gargling_id, service=service.name
        )
        conn.commit()
    return Response(status=200)


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
                user_report += f"Body fat percentage er *{fat}*. "
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
    users = [init_user(dict(token)) for token in tokens]
    steps_data = steps(conn, users, date)
    body_data = get_body_data(users, date)
    body_reports = body_details(body_data)
    return steps_data, body_reports
