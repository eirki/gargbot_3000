#! /usr/bin/env python3.6
# coding: utf-8
import contextlib
import json
import os
import typing as t

import requests
from flask import Flask, Response, jsonify, render_template, request
from gunicorn.app.base import BaseApplication

from gargbot_3000 import commands, config, database_manager, droppics, quotes
from gargbot_3000.logger import log

app = Flask(__name__)
app.pool = database_manager.ConnectionPool()
app.drop_pics = None
app.quotes_db = None


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


def interaction_share(data: dict) -> dict:
    response_url = data["response_url"]
    delete_ephemeral(response_url)
    result = json.loads(data["actions"][0]["value"])["original_response"]
    log.info("Interactive: share")
    result["replace_original"] = False
    result["response_type"] = "in_channel"
    return result


def interaction_cancel() -> dict:
    result = {
        "response_type": "ephemeral",
        "replace_original": True,
        "text": (
            "Canceled! Går fint det. Ikke noe problem for meg. "
            "Hadde ikke lyst uansett."
        ),
    }
    return result


def interaction_shuffle(data: dict) -> dict:
    original_func = json.loads(data["actions"][0]["value"])["original_func"]
    original_args = json.loads(data["actions"][0]["value"])["original_args"]
    callback_id = data["callback_id"]
    result = handle_command(original_func, original_args, callback_id)
    result["replace_original"] = True
    return result


@app.route("/interactive", methods=["POST"])
def interactive() -> Response:
    log.info("incoming interactive request:")
    data = json.loads(request.form["payload"])
    log.info(data)
    if not data.get("token") == config.slack_verification_token:
        return Response(status=403)
    action = data["actions"][0]["name"]
    log.info(f"Interactive: {action}")
    if action == "share":
        result = interaction_share(data)
    elif action == "cancel":
        result = interaction_cancel()
    elif action == "shuffle":
        result = interaction_shuffle(data)
    elif action in {"pic", "forum", "msn"}:
        trigger_id = data["trigger_id"]
        result = handle_command(command_str=action, args=[], trigger_id=trigger_id)
    else:
        raise Exception(f"Unknown action: {action}")
    return jsonify(result)


@app.route("/slash", methods=["POST"])
def slash_cmds() -> Response:
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


def handle_command(command_str: str, args: list, trigger_id: str) -> dict:
    db_func = (
        app.pool.get_db_connection
        if command_str in {"hvem", "pic", "forum", "msn"}
        else contextlib.nullcontext
    )
    with db_func() as db:
        result = commands.execute(
            command_str=command_str,
            args=args,
            db_connection=db,
            drop_pics=app.drop_pics,
            quotes_db=app.quotes_db,
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
        pic_url, *_ = app.drop_pics.get_pic(db, arg_list=config.countdown_args)
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
    try:
        app.pool.setup()
        with app.pool.get_db_connection() as db:
            app.drop_pics = droppics.DropPics(db=db)
            app.quotes_db = quotes.Quotes(db=db)
        if debug is False:
            gunicorn_app = StandaloneApplication(app, options)
            gunicorn_app.run()
        else:
            # Workaround for a werzeug reloader bug
            # (https://github.com/pallets/flask/issues/1246)
            os.environ["PYTHONPATH"] = os.getcwd()
            app.run(debug=True)
    except Exception:
        log.error("Error in server setup", exc_info=True)
    finally:
        if app.pool.is_setup:
            app.pool.closeall()
