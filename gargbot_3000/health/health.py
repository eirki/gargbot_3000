#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import typing as t

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum
from psycopg2.extensions import connection
import withings_api

from gargbot_3000.health.common import queries
from gargbot_3000.health.fitbit_ import FitbitService, FitbitUser
from gargbot_3000.health.googlefit import GooglefitService, GooglefitUser
from gargbot_3000.health.polar import PolarService, PolarUser
from gargbot_3000.health.withings import WithingsService, WithingsUser
from gargbot_3000.logger import log

withings_api.common.enforce_type = lambda value, expected: value

blueprint = Blueprint("health", __name__)

HealthService = t.Union[FitbitService, GooglefitService, PolarService, WithingsService]
HealthUser = t.Union[FitbitUser, GooglefitUser, PolarUser, WithingsUser]


def init_service(service_name: str) -> HealthService:
    services: dict[str, t.Type[HealthService]] = {
        "fitbit": FitbitService,
        "googlefit": GooglefitService,
        "polar": PolarService,
        "withings": WithingsService,
    }
    service = services[service_name]()
    return service


def init_user(token: dict) -> HealthUser:
    services: dict[str, t.Type[HealthUser]] = {
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
    service = init_service(service_name)
    url = service.authorization_url()
    response = jsonify(is_registered=False, auth_url=url)
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
                conn,
                gargling_id=gargling_id,
                token_table=f"{service.name}_token",
                token_gargling_table=f"{service.name}_token_gargling",
            )
            is not None
        ):
            service_user_id_ = queries.service_user_id_for_gargling_id(
                conn,
                gargling_id=gargling_id,
                token_gargling_table=f"{service.name}_token_gargling",
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
                token_gargling_table=f"{service.name}_token_gargling",
            )
        conn.commit()
    return Response(status=200)


@blueprint.route("/health_toggle", methods=["POST"])
@jwt_required
def toggle():
    gargling_id = get_jwt_identity()
    content = request.json
    service = init_service(content["service"])
    measure = content["measure"]
    if measure not in {"steps", "weight"}:
        raise Exception
    enable = content["enable"]
    with current_app.pool.get_connection() as conn:
        if enable:
            queries.disable_services(
                conn, gargling_id=gargling_id, type_col=f"enable_{measure}",
            )
        queries.toggle_service(
            conn,
            enable_=enable,
            gargling_id=gargling_id,
            type_col=f"enable_{measure}",
            token_table=f"{service.name}_token",
            token_gargling_table=f"{service.name}_token_gargling",
        )

        conn.commit()
    return Response(status=200)


@blueprint.route("/health_status")
@jwt_required
def health_status():
    gargling_id = get_jwt_identity()
    with current_app.pool.get_connection() as conn:
        data = queries.health_status(conn, gargling_id=gargling_id)
    as_dict = {row["service"]: dict(row) for row in data}
    return jsonify(data=as_dict)


def steps(conn: connection, users: list[HealthUser], date: pendulum.Date) -> list[dict]:
    step_amounts = []
    for user in users:
        try:
            amount = (
                user.steps(date)
                if not isinstance(user, PolarUser)
                else user.steps(date, conn)
            )
        except Exception:
            log.error(
                f"Error getting {user.service.name} steps data for {user.first_name}",
                exc_info=True,
            )
            continue
        if amount is None:
            continue
        step_amounts.append({"amount": amount, "gargling_id": user.gargling_id})
    return step_amounts


def get_body_data(users: list[HealthUser], date: pendulum.Date) -> list[dict]:
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


def body_details(body_data: list[dict]) -> t.Optional[list]:
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
    step_users, weight_users = [], []
    for token in tokens:
        token = dict(token)
        enable_steps = token.pop("enable_steps")
        enable_weight = token.pop("enable_weight")
        if not (enable_steps or enable_weight):
            continue
        user = init_user(token)
        if enable_steps:
            step_users.append(user)
        if enable_weight:
            weight_users.append(user)
    steps_data = steps(conn, step_users, date)
    body_data = get_body_data(weight_users, date)
    body_reports = body_details(body_data)
    return steps_data, body_reports
