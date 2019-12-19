#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import typing as t

import aiosql
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
from wtforms import Form, RadioField, SelectField, SubmitField

from gargbot_3000 import config
from gargbot_3000 import database_manager as db
from gargbot_3000.logger import log

blueprint = Blueprint("health", __name__)
blueprint.fitbit = None  # type: ignore

queries = aiosql.from_path("schema/health.sql", "psycopg2")


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
    url = url_for("health.whoisyou", fitbit_id=token["user_id"], _external=True)
    return redirect(url)


class WhoIsForm(Form):
    name = SelectField("who the hell is you", choices=[("", "select")])
    report = RadioField(
        "Enable daglig vektrapportering?",
        choices=[("yes", "Hell yes!"), ("no", "Nai")],
        default=True,
    )
    ok = SubmitField(label="OK")


@blueprint.route("/whoisyou/<fitbit_id>", methods=("GET", "POST"))
def whoisyou(fitbit_id: str):
    with current_app.pool.get_db_connection() as conn:
        if queries.is_fitbit_user(conn, fitbit_id=fitbit_id) is None:
            return abort(403)
        form = WhoIsForm(request.form)
        if request.method == "POST":
            if form.report.data == "yes":
                queries.enable_daily_report(conn, fitbit_id=fitbit_id)
            elif form.report.data == "no":
                queries.disable_daily_report(conn, fitbit_id=fitbit_id)
            db_id = form.name.data
            if db_id != "":
                queries.match_ids(conn, db_id=db_id, fitbit_id=fitbit_id)
                conn.commit()
                return "Fumbs up!"
            else:
                if queries.is_id_matched(conn, fitbit_id=fitbit_id):
                    return "Fumbs up!"
        data = queries.get_nicks_ids(conn)
        form.name.choices.extend([(row["db_id"], row["slack_nick"]) for row in data])
    return render_template("whoisyou.html", form=form)


def persist_token(token: t.Dict) -> None:
    try:
        with current_app.pool.get_db_connection() as conn:
            queries.persist_token(conn, **token)
            conn.commit()
    except RuntimeError:
        conn = db.connect_to_database()
        queries.persist_token(conn, **token)
        conn.commit()
        conn.close()


def parse_report_args(
    conn: db.connection, args: t.List[str], all_topics: t.Set[str]
) -> t.Tuple[t.Set[str], t.List[dict], t.Set[str], t.Set[str]]:
    topics = all_topics.intersection(args)

    users = set(
        row["slack_nick"] for row in queries.parse_nicks_from_args(conn, args=args)
    )
    tokens: t.List[dict] = [
        dict(data)
        for data in queries.get_fitbit_tokens_by_slack_nicks(
            conn, slack_nicks=list(users)
        )
    ]
    users_authed = {token["slack_nick"] for token in tokens}
    users_nonauthed = users - users_authed

    invalid_args = set(args) - topics - users_authed - users_nonauthed
    return topics, tokens, users_nonauthed, invalid_args


def init_fitbit_clients(tokens: t.List[dict]) -> t.Dict[str, Fitbit]:
    clients = {
        token["slack_nick"]: Fitbit(
            config.fitbit_client_ID,
            config.fitbit_client_secret,
            access_token=token["access_token"],
            refresh_token=token["refresh_token"],
            expires_at=token["expires_at"],
            refresh_cb=persist_token,
            system=Fitbit.METRIC,
        )
        for token in tokens
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


def report(args: t.Optional[t.List[str]], conn: db.connection):
    topics_switch = {
        "vekt": get_weight,
        "aktivitet": get_activity,
        "søvn": get_sleep,
        "puls": get_heartrate,
    }

    all_topics = set(topics_switch)
    topics: t.Set[str] = set()
    tokens: t.List[dict] = []
    users_nonauthed: t.Set[str] = set()
    invalid_args: t.Set[str] = set()

    if args:
        topics, tokens, users_nonauthed, invalid_args = parse_report_args(
            conn, args, all_topics
        )
    if not topics:
        topics = all_topics
    if not tokens:
        tokens = queries.get_all_fitbit_tokens(conn)

    clients = init_fitbit_clients(tokens)

    log.info(f"Args: {args}")
    log.info(f"Topics: {topics}")
    log.info(f"Users: {list(clients)}")
    log.info(f"Users Nonauthed: {users_nonauthed}")
    log.info(f"Invalid args: {invalid_args}")

    data = {
        topic: {nick: topics_switch[topic](client) for nick, client in clients.items()}
        for topic in topics
    }
    return data, invalid_args, users_nonauthed


def send_daily_report(conn: db.connection) -> t.Optional[dict]:
    tokens = queries.get_daily_report_tokens(conn)
    if not tokens:
        return None
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
