#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from asyncio import Future
import typing as t

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum
from psycopg2.extensions import connection
import slack
import withings_api

from gargbot_3000 import config, database
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
    if gargling_id is None:  # no test coverage
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
    if gargling_id is None:  # no test coverage
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
            if isinstance(service, GooglefitService):  # no test coverage
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
    if measure not in {"steps", "weight"}:  # no test coverage
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
        reminder_users = queries.get_sync_reminder_users(conn)
    as_dict: dict[str, t.Any] = {row["service"]: dict(row) for row in data}
    is_reminder_user = any(user["id"] == gargling_id for user in reminder_users)
    as_dict["is_reminder_user"] = is_reminder_user
    return jsonify(data=as_dict)


@blueprint.route("/toggle_sync_reminder", methods=["POST"])
@jwt_required
def toggle_sync_reminder():
    gargling_id = get_jwt_identity()
    enable = request.json["enable"]
    with current_app.pool.get_connection() as conn:
        queries.toggle_sync_reminding(conn, enable_=enable, id=gargling_id)
        conn.commit()
    return Response(status=200)


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
        if amount is None:  # no test coverage
            continue
        step_amounts.append(
            {"amount": amount, "gargling_id": user.gargling_id},
        )  # no test coverage
    return step_amounts


def get_body_data(users: list[HealthUser], date: pendulum.Date) -> list[dict]:
    all_data = []
    for user in users:  # no test coverage
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
) -> t.Optional[tuple[list, t.Optional[list]]]:
    tokens = queries.tokens(conn)
    if not tokens:  # no test coverage
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
        if enable_weight:  # no test coverage
            weight_users.append(user)
    steps_data = steps(conn, step_users, date)
    body_data = get_body_data(weight_users, date)
    body_reports = body_details(body_data)
    return steps_data, body_reports


def send_sync_reminders(conn: connection, slack_client, steps_data) -> None:
    reminder_users = queries.get_sync_reminder_users(conn)
    reminder_users_by_id = {user["id"]: user for user in reminder_users}
    for datum in steps_data:
        try:
            user_data = reminder_users_by_id[datum["gargling_id"]]
        except KeyError:
            continue
        msg = (
            f"Du gikk {datum['amount']} skritt i går, by my preliminary calculations. "
            "Husk å synce hvis dette tallet er for lavt. "
            f"Denne reminderen kan skrus av <{config.server_name}/health|her>. Stay "
            "beautiful, doll-face!"
        )
        try:
            resp = slack_client.chat_postMessage(
                text=msg, channel=user_data["slack_id"]
            )
            if isinstance(resp, Future):  # no test coverage
                # satisfy mypy
                raise Exception()
            if resp.data.get("ok") is True:
                queries.update_reminder_ts(
                    conn, ts=resp.data["ts"], id=datum["gargling_id"]
                )
                conn.commit()
        except Exception:  # no test coverage
            log.error(
                f"Error sending sync reminder for user id: {user_data['slack_id']}",
                exc_info=True,
            )


def delete_sync_reminders(conn: connection, slack_client) -> None:
    reminder_users = queries.get_sync_reminder_users(conn)
    log.info(reminder_users)
    for user in reminder_users:
        if user["last_sync_reminder_ts"] is None:  # no test coverage
            continue
        try:
            slack_client.chat_delete(
                channel=user["slack_id"], ts=user["last_sync_reminder_ts"]
            )
        except Exception:  # no test coverage
            log.error(
                f"Error deleting sync reminder for user id: {user['id']}",
                exc_info=True,
            )
        queries.update_reminder_ts(conn, ts=None, id=user["id"])
        conn.commit()


def run_sync_deleting() -> None:  # no test coverage
    conn = database.connect()
    slack_client = slack.WebClient(config.slack_bot_user_token)
    try:
        delete_sync_reminders(conn, slack_client)
    finally:
        conn.close()


def run_sync_reminding() -> None:  # no test coverage
    conn = database.connect()
    current_date = pendulum.now()
    date = current_date.subtract(days=1)
    data = activity(conn, date)
    if data is None:
        return
    steps_data, body_reports = data
    slack_client = slack.WebClient(config.slack_bot_user_token)
    try:
        send_sync_reminders(conn, slack_client, steps_data)
    finally:
        conn.close()
