#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

# Core
import json

# Dependencies
import requests
from flask import Flask, request, g, Response, render_template

# Internal
from gargbot_3000 import config
from gargbot_3000 import commands
from gargbot_3000 import database_manager
from gargbot_3000 import quotes
from gargbot_3000 import droppics

# Typing
from typing import Dict, List, Optional

app = Flask(__name__)


def get_db():
    db_connection = getattr(g, "_database", None)
    if db_connection is None:
        db_connection = database_manager.connect_to_database()
        g._database = db_connection
    return db_connection


@app.teardown_appcontext
def close_connection(exception):
    db_connection = getattr(g, "_database", None)
    if db_connection is not None:
        database_manager.close_database_connection(db_connection)


def get_pics():
    drop_pics = getattr(g, "_drop_pics", None)
    if drop_pics is None:
        drop_pics = droppics.DropPics(db=get_db())
        g._drop_pics = drop_pics
    return drop_pics


def get_quotes():
    quotes_db = getattr(g, "_quotes_db", None)
    if quotes_db is None:
        quotes_db = quotes.Quotes(db=get_db())
        g._quotes_db = quotes_db
    return quotes_db


def json_response(result: Dict) -> Response:
    return Response(
        response=json.dumps(result), status=200, mimetype="application/json"
    )


def attach_buttons(callback_id, result, func, args):
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
        {
            "name": "cancel",
            "text": "Avbryt",
            "value": "avbryt",
            "type": "button",
            "style": "danger",
        },
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


@app.route("/")
def hello_world() -> str:
    return "home"


def delete_ephemeral(response_url):
    delete_original = {
        "response_type": "ephemeral",
        "replace_original": True,
        "text": "Sharing is caring!",
    }
    r = requests.post(response_url, json=delete_original)
    log.info(r.text)


def share(result):
    log.info("Interactive: share")
    result["replace_original"] = False
    result["response_type"] = "in_channel"
    return json_response(result)


def cancel():
    log.info("Interactive: cancel")
    result = {
        "response_type": "ephemeral",
        "replace_original": True,
        "text": "Canceled! Går fint det. Ikke noe problem for meg. Hadde ikke lyst uansett.",
    }
    return json_response(result)


def shuffle(callback_id: str, original_func: str, original_args: List[Optional[str]]):
    log.info("Interactive: shuffle")
    result = handle_command(original_func, original_args, callback_id)
    result["replace_original"] = True
    return json_response(result)


@app.route("/interactive", methods=["POST"])
def interactive():
    log.info("incoming interactive request:")
    data = json.loads(request.form["payload"])
    log.info(data)
    if not data.get("token") == config.slack_verification_token:
        return Response(status=403)
    action = data["actions"][0]["name"]

    if action == "share":
        response_url = data["response_url"]
        delete_ephemeral(response_url)
        result = json.loads(data["actions"][0]["value"])["original_response"]
        return share(result)
    elif action == "cancel":
        return cancel()
    elif action == "shuffle":
        original_req = json.loads(data["actions"][0]["value"])
        callback_id = data["callback_id"]
        return shuffle(callback_id, **original_req)


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
    return json_response(result)


def handle_command(command_str: str, args: List, trigger_id: str) -> Dict:
    db = get_db() if command_str in {"hvem", "pic", "quote", "msn"} else None
    pic = get_pics() if command_str == "pic" else None
    quotes = get_quotes() if command_str in {"quote", "msn"} else None
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
    elif command_str in {"pic", "quote", "msn"}:
        result = attach_buttons(
            callback_id=trigger_id, result=result, func=command_str, args=args
        )
    return result


@app.route("/countdown", methods=["GET"])
def countdown():
    milli_timestamp = config.countdown_date.timestamp() * 1000
    db = get_db()
    drop_pics = get_pics()
    pic_url, *_ = drop_pics.get_pic(db, arg_list=config.countdown_args)
    return render_template(
        "countdown.html",
        date=milli_timestamp,
        image_url=pic_url,
        countdown_message=config.countdown_message,
        ongoing_message=config.ongoing_message,
        finished_message=config.finished_message,
    )


def main():
    log.info("GargBot 3000 server operational!")
    app.run()


if __name__ == "__main__":
    main()
