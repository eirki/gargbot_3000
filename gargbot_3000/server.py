#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log
import json
from copy import deepcopy

from flask import Flask, request, g, Response

from gargbot_3000 import config
from gargbot_3000 import commands
from gargbot_3000 import database_manager
from gargbot_3000 import quotes
from gargbot_3000 import droppics

app = Flask(__name__)


def get_db():
    db_connection = getattr(g, '_database', None)
    if db_connection is None:
        db_connection = database_manager.connect_to_database()
        g._database = db_connection
    return db_connection


@app.teardown_appcontext
def close_connection(exception):
    db_connection = getattr(g, '_database', None)
    if db_connection is not None:
        db_connection.close()


def attach_buttons(callback_id, result, func, args):
    actions = [
            {
                "name": "Send",
                "text": "send",
                "type": "button",
                "style": "primary",
                "value": json.dumps({"original_response": result})
            },
            {
                "name": "Shuffle",
                "text": "shuffle",
                "type": "button",
                "value": json.dumps({"original_func": func, "original_args": args})
            },
            {
                "name": "Avbryt",
                "text": "avbryt",
                "value": "avbryt",
                "type": "button",
                "style": "danger"
            },
    ]
    result["attachments"][0]["actions"] = actions
    result["attachments"][0]["callback_id"] = callback_id


@app.route('/')
def hello_world() -> str:
    return "home"


@app.route('/interactive', methods=['POST'])
def interactive():
    log.info("incoming interactive request:")
    data = json.loads(request.form['payload'])
    log.info(data)
    if not data.get('token') == config.v2_verification_token:
        return Response(status=403)
    action = data["actions"][0]["name"]
    if action == "Send":
        log.info("Interactive: Send")
        result = json.loads(data["actions"][0]["value"])["original_response"]
        result["response_type"] = "in_channel"
        del result["attachments"]["actions"]
        return Response(
            response=json.dumps(result),
            status=200,
            mimetype='application/json'
        )

    elif action == "Avbryt":
        log.info("Interactive: Avbryt")
        #  Unfinished
        result = {
            "response_type": "ephemeral",
            "replace_original": True,
            "text": "Canceled!"
        }
        return Response(
            status=200,
            response=json.dumps(result),
            mimetype='application/json'
        )

    elif action == "Shuffle":
        log.info("Interactive: Shuffle")
        callback_id = data["callback_id"]
        command_str = json.loads(data["actions"][0]["value"])["original_func"]
        args = json.loads(data["actions"][0]["value"])["original_args"]

        # duplicate code follows
        log.info(f"command: {command_str}")
        log.info(f"args: {args}")

        try:
            command_function = commands.command_switch[command_str]
        except KeyError:
            command_function = commands.cmd_not_found
            args = [command_str]

        if command_str in {"msn", "quote", "pic"}:
            db_connection = get_db()
            command_function.keywords["db"] = db_connection

        result = commands.try_or_panic(command_function, args)
        if not result.get("text", "").startswith("Error"):
            attach_buttons(
                callback_id=callback_id,
                result=result,
                func=command_str,
                args=args
            )
            result["response_type"] = "ephemeral"
        log.info(f"result: {result}")
        return Response(
            response=json.dumps(result),
            status=200,
            mimetype='application/json'
        )


@app.route('/slash', methods=['POST'])
def slash_cmds():
    log.info("incoming slash request:")
    data = request.form
    log.info(data)
    trigger_id = data["trigger_id"]

    if not data.get('token') == config.v2_verification_token:
        return Response(status=403)
    command_str = data["command"][1:]
    args = data['text']
    log.info(f"command: {command_str}")
    log.info(f"args: {args}")

    try:
        command_function = commands.command_switch[command_str]
    except KeyError:
        command_function = commands.cmd_not_found
        args = [command_str]

    if command_str in {"msn", "quote", "pic"}:
        db_connection = get_db()
        command_function.keywords["db"] = db_connection

    result = commands.try_or_panic(command_function, args)
    result["response_type"] = "ephemeral"
    attach_buttons(
        callback_id=trigger_id,
        result=result,
        func=command_str,
        args=args
    )
    log.info(f"result: {result}")
    return Response(
        response=json.dumps(result),
        status=200,
        mimetype='application/json'
    )


def setup():
    db_connection = database_manager.connect_to_database()
    quotes_db = quotes.Quotes(db=db_connection)
    commands.command_switch["msn"].keywords["quotes_db"] = quotes_db
    commands.command_switch["quote"].keywords["quotes_db"] = quotes_db

    drop_pics = droppics.DropPics(db=db_connection)
    drop_pics.connect_dbx()
    commands.command_switch["pic"].keywords["drop_pics"] = drop_pics


def main():
    setup()
    log.info("GargBot 3000 server operational!")
    # app.run() uwsgi does this
    pass


if __name__ == '__main__':
    main()
