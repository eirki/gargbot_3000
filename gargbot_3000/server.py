#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

# Core
import json
import os
import contextlib

# Dependencies
import requests
from flask import Flask, request, g, Response, render_template, jsonify
from gunicorn.app.base import BaseApplication

# Internal
from gargbot_3000 import config
from gargbot_3000 import commands
from gargbot_3000 import database_manager
from gargbot_3000 import quotes
from gargbot_3000 import droppics

# Typing
import typing as t
from typing import Dict, List
from psycopg2.extensions import connection

app = Flask(__name__)
app.pool = database_manager.ConnectionPool()


def get_pics(db: connection):
    drop_pics = getattr(g, "_drop_pics", None)
    if drop_pics is None:
        drop_pics = droppics.DropPics(db=db)
        g._drop_pics = drop_pics
    return drop_pics


def get_quotes(db: connection):
    quotes_db = getattr(g, "_quotes_db", None)
    if quotes_db is None:
        quotes_db = quotes.Quotes(db=db)
        g._quotes_db = quotes_db
    return quotes_db


def attach_share_buttons(callback_id, result, func, args):
    actions = [
        {
            "name": "share",
            "text": "Del i kanal",
            "type": "button",
            "style": "primary",
            "value": json.dumps({"original_response": result}),
        },
        {
            "name": "shuffle",
            "text": "Shuffle",
            "type": "button",
            "value": json.dumps({"original_func": func, "original_args": args}),
        },
        {"name": "cancel", "text": "Avbryt", "type": "button", "style": "danger"},
    ]
    try:
        attachment = result["attachments"][-1]
    except KeyError:
        attachment = {}
        result["attachments"] = [attachment]
    attachment["actions"] = actions
    attachment["callback_id"] = callback_id
    result["response_type"] = "ephemeral"
    return result


def attach_commands_buttons(callback_id, result) -> dict:
    attachments = [
        {
            "text": "Try me:",
            "actions": [
                {"name": "pic", "text": "/pic", "type": "button"},
                {"name": "forum", "text": "/forum", "type": "button"},
                {"name": "msn", "text": "/msn", "type": "button"},
            ],
            "callback_id": callback_id,
        }
    ]
    result["attachments"] = attachments
    result["replace_original"] = True
    return result


@app.route("/")
def hello_world() -> str:
    return "home"


def delete_ephemeral(response_url: str):
    delete_original = {
        "response_type": "ephemeral",
        "replace_original": True,
        "text": "Sharing is caring!",
    }
    r = requests.post(response_url, json=delete_original)
    log.info(r.text)


def handle_share_interaction(action: str, data: dict):
    if action == "share":
        response_url = data["response_url"]
        delete_ephemeral(response_url)
        result = json.loads(data["actions"][0]["value"])["original_response"]
        log.info("Interactive: share")
        result["replace_original"] = False
        result["response_type"] = "in_channel"
    elif action == "cancel":
        log.info("Interactive: cancel")
        result = {
            "response_type": "ephemeral",
            "replace_original": True,
            "text": "Canceled! Går fint det. Ikke noe problem for meg. Hadde ikke lyst uansett.",
        }
    elif action == "shuffle":
        log.info("Interactive: shuffle")
        original_func = json.loads(data["actions"][0]["value"])["original_func"]
        original_args = json.loads(data["actions"][0]["value"])["original_args"]
        callback_id = data["callback_id"]
        result = handle_command(original_func, original_args, callback_id)
        result["replace_original"] = True
    return result


@app.route("/interactive", methods=["POST"])
def interactive():
    log.info("incoming interactive request:")
    data = json.loads(request.form["payload"])
    log.info(data)
    if not data.get("token") == config.slack_verification_token:
        return Response(status=403)
    action = data["actions"][0]["name"]
    if action in {"share", "shuffle", "cancel"}:
        result = handle_share_interaction(action, data)
    elif action in {"pic", "forum", "msn"}:
        trigger_id = data["trigger_id"]
        result = handle_command(command_str=action, args=[], trigger_id=trigger_id)
    else:
        raise Exception(f"Unknown action: {result}")
    return jsonify(result)


@app.route("/slash", methods=["POST"])
def slash_cmds():
    log.info("incoming slash request:")
    data = request.form
    log.info(data)

    if not data.get("token") == config.slack_verification_token:
        return Response(status=403)

    command_str = data["command"][1:]
    args = data["text"]
    args = args.replace("@", "").split()

    trigger_id = data["trigger_id"]
    result = handle_command(command_str, args, trigger_id)
    log.info(f"result: {result}")
    return jsonify(result)


def handle_command(command_str: str, args: List, trigger_id: str) -> Dict:
    db_func = (
        app.pool.get_db_connection
        if command_str in {"hvem", "pic", "forum", "msn"}
        else contextlib.nullcontext
    )
    with db_func() as db:
        pic = get_pics(db) if command_str == "pic" else None
        quotes = get_quotes(db) if command_str in {"forum", "msn"} else None
        result = commands.execute(
            command_str=command_str,
            args=args,
            db_connection=db,
            drop_pics=pic,
            quotes_db=quotes,
        )

    error = result.get("text", "").startswith("Error")
    if error:
        return result
    if command_str in {"ping", "hvem"}:
        result["response_type"] = "in_channel"
    elif command_str in {"pic", "forum", "msn"}:
        result = attach_share_buttons(
            callback_id=trigger_id, result=result, func=command_str, args=args
        )
    elif command_str == "gargbot":
        result = attach_commands_buttons(callback_id=trigger_id, result=result)
    return result


@app.route("/countdown", methods=["GET"])
def countdown():
    milli_timestamp = config.countdown_date.timestamp() * 1000
    with app.pool.get_db_connection() as db:
        drop_pics = get_pics(db)
        pic_url, *_ = drop_pics.get_pic(db, arg_list=config.countdown_args)
    return render_template(
        "countdown.html",
        date=milli_timestamp,
        image_url=pic_url,
        countdown_message=config.countdown_message,
        ongoing_message=config.ongoing_message,
        finished_message=config.finished_message,
    )


class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options if options is not None else {}
        self.application = app
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main(options: t.Optional[dict], debug: bool = False):
    app.pool.setup()
    if debug is False:
        gunicorn_app = StandaloneApplication(app, options)
        gunicorn_app.run()
    else:
        # Workaround for a werzeug reloader bug
        # (https://github.com/pallets/flask/issues/1246)
        os.environ["PYTHONPATH"] = os.getcwd()
        app.run(debug=True)
    app.pool.closeall()
