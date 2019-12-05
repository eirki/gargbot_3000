#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import typing as t

import pendulum
from fitbit import Fitbit
from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from wtforms import Form, SelectField, SubmitField

from gargbot_3000 import config
from gargbot_3000 import database_manager as db
from gargbot_3000.database_manager import LoggingCursor as Cursor
from gargbot_3000.logger import log

blueprint = Blueprint("health", __name__)
blueprint.fitbit = None  # type: ignore


def setup_bluebrint():
    blueprint.fitbit = Fitbit(
        config.fitbit_client_ID,
        config.fitbit_client_secret,
        redirect_uri=config.fitbit_redirect_uri,
        timeout=10,
    )


@blueprint.route("/fitbit-auth", methods=["GET"])
def authorize_user():
    scope = ["activity", "heartrate", "profile", "sleep", "weight"]
    url, _ = blueprint.fitbit.client.authorize_token_url(scope=scope)
    return redirect(url)


@blueprint.route("/fitbit-redirect", methods=["GET"])
def handle_redirect():
    code = request.args["code"]
    blueprint.fitbit.client.fetch_access_token(code)
    token = blueprint.fitbit.client.session.token
    persist_token(token)
    return redirect(url_for("health.whoisyou", fitbit_id=token["user_id"]))


class WhoIsForm(Form):
    name = SelectField("who the hell is you", choices=[("", "select")])
    ok = SubmitField(label="OK")


@blueprint.route("/whoisyou/<fitbit_id>", methods=("GET", "POST"))
def whoisyou(fitbit_id: str):
    with current_app.pool.get_db_cursor(commit=True) as cursor:
        sql = "SELECT TRUE FROM fitbit WHERE fitbit_id = %(fitbit_id)s"
        cursor.execute(sql, {"fitbit_id": fitbit_id})
        if cursor.fetchone() is None:
            return abort(403)
        form = WhoIsForm(request.form)
        if request.method == "POST":
            slack_nick = form.name.data
            if slack_nick != "":
                match_ids(cursor, slack_nick, fitbit_id)
                return "Fumbs up!"
        sql = "SELECT slack_nick FROM user_ids"
        cursor.execute(sql)
        data = cursor.fetchall()
        form.name.choices.extend(
            [(row["slack_nick"], row["slack_nick"]) for row in data]
        )
    return render_template("whoisyou.html", form=form)


def match_ids(cursor: Cursor, slack_nick: str, fitbit_id: str) -> None:
    sql = (
        "UPDATE fitbit SET slack_nick = %(slack_nick)s WHERE fitbit_id = %(fitbit_id)s"
    )
    data = {"slack_nick": slack_nick, "fitbit_id": fitbit_id}
    cursor.execute(sql, data)


def persist_token(token: t.Dict) -> None:
    sql = (
        "INSERT INTO fitbit "
        "(fitbit_id, access_token, refresh_token, expires_at) "
        "VALUES "
        "(%(user_id)s, %(access_token)s, %(refresh_token)s, %(expires_at)s) "
        "ON CONFLICT (fitbit_id) DO UPDATE SET "
        "(access_token, refresh_token, expires_at) = "
        "(EXCLUDED.access_token, EXCLUDED.refresh_token, EXCLUDED.expires_at)"
    )
    try:
        with current_app.pool.get_db_cursor(commit=True) as cursor:
            cursor.execute(sql, token)
    except RuntimeError:
        connection = db.connect_to_database()
        with connection.cursor() as cursor:
            cursor.execute(sql, token)
            connection.commit()


def get_all_users(cursor: Cursor) -> t.Dict[str, int]:
    sql_command = "SELECT db_id, slack_nick FROM user_ids"
    cursor.execute(sql_command)
    users = {row["slack_nick"]: row["db_id"] for row in cursor.fetchall()}
    return users


def get_fitbit_users(cursor: Cursor) -> t.Dict[int, dict]:
    sql_command = "SELECT * FROM fitbit"
    cursor.execute(sql_command)
    data = cursor.fetchall()
    users = {}
    for row in data:
        row = dict(row)
        db_id = row.pop("db_id")
        if db_id is None:
            continue
        users[db_id] = row
    return users


def parse_report_args(
    args: t.List[str],
    all_topics: t.List[str],
    all_users: t.Dict[str, int],
    all_fitbit_users: t.Dict[int, dict],
):
    topics: t.List[str] = []
    tokens: t.Dict[str, dict] = {}
    users_nonauthed: t.List[str] = []
    invalid_args: t.List[str] = []

    for arg in args:
        if arg in all_topics:
            topics.append(arg)
        elif arg in all_users:
            db_id = all_users[arg]
            try:
                token = all_fitbit_users[db_id]
                tokens[arg] = token
            except KeyError:
                users_nonauthed.append(arg)
        else:
            invalid_args.append(arg)
    return (topics, tokens, users_nonauthed, invalid_args)


def init_fitbit_clients(tokens: t.Dict[str, dict]) -> t.Dict[str, Fitbit]:
    clients = {
        slack_nick: Fitbit(
            config.fitbit_client_ID,
            config.fitbit_client_secret,
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            expires_at=token["expires_at"],
            refresh_cb=persist_token,
            system=Fitbit.METRIC,
        )
        for slack_nick, token in tokens.items()
    }
    return clients


def get_weight(client: Fitbit) -> dict:
    data = client.get_bodyweight(period="1m")
    rec = data["weight"][0]
    date_obj = pendulum.parse(f"{rec['date']}T{rec['time']}")
    rec["datetime"] = date_obj
    log.info(f"weight data: {rec}")
    return rec


def get_activity(client: Fitbit) -> str:
    data = client.recent_activities()
    log.info(f"activity data: {data}")
    return data


def get_sleep(client: Fitbit) -> str:
    data = client.get_sleep(date=dt.datetime.today())
    log.info(f"sleep data: {data}")
    return data


def get_heartrate(client: Fitbit) -> str:
    data = client.time_series("activities/heart", period="1d")
    log.info("heartrate data:", data)
    return data


def report(args: t.Optional[t.List[str]], connection: db.connection):
    topics_switch = {
        "vekt": get_weight,
        "aktivitet": get_activity,
        "søvn": get_sleep,
        "puls": get_heartrate,
    }
    with connection.cursor() as cursor:
        all_fitbit_users = get_fitbit_users(cursor)
        all_users = get_all_users(cursor)

    all_topics = list(topics_switch)
    ids_to_nics = {db_id: slack_nick for slack_nick, db_id in all_users.items()}
    all_tokens = {
        ids_to_nics[db_id]: token for db_id, token in all_fitbit_users.items()
    }
    topics: t.List[str] = []
    tokens: t.Dict[str, dict] = {}
    users_nonauthed: t.List[str] = []
    invalid_args: t.List[str] = []
    if args:
        topics, tokens, users_nonauthed, invalid_args = parse_report_args(
            args, all_topics, all_users, all_fitbit_users
        )
    if not topics:
        topics = all_topics
    if not tokens:
        tokens = all_tokens
    log.info(f"Topics: {topics}")
    log.info(f"Invalid args: {invalid_args}")

    clients = init_fitbit_clients(tokens)
    data = {
        topic: {nick: topics_switch[topic](client) for nick, client in clients.items()}
        for topic in topics
    }
    return data, invalid_args, users_nonauthed


def get_report_users(cursor: Cursor) -> t.List[int]:
    sql = "SELECT db_id FROM health_report"
    cursor.execute(sql)
    db_ids = [row["db_id"] for row in cursor.fetchall()]
    return db_ids


def send_daily_report(connection: db.connection) -> dict:
    with connection.cursor() as cursor:
        all_fitbit_users = get_fitbit_users(cursor)
        all_users = get_all_users(cursor)
        report_users = set(get_report_users(cursor))
    ids_to_nics = {db_id: slack_nick for slack_nick, db_id in all_users.items()}
    tokens = {
        ids_to_nics[db_id]: token
        for db_id, token in all_fitbit_users.items()
        if db_id in report_users
    }
    clients = init_fitbit_clients(tokens)
    data = {nick: get_weight(client) for nick, client in clients.items()}
    now = pendulum.now()
    weight_descriptions = [
        f"{nick} veier nå *{datum['weight']}* kg!"
        if (now - datum["datetime"]).days < 2
        else (
            f"{nick} har ikke veid seg på *{(now - datum['datetime']).days}* dager. "
            "Skjerpings!"
        )
        for nick, datum in data.items()
    ]
    response = {
        "text": "Attention garglings!",
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Attention garglings:*"},
            }
        ]
        + [
            {"type": "section", "text": {"type": "mrkdwn", "text": desc}}
            for desc in weight_descriptions
        ],
    }
    return response
