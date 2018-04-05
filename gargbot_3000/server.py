#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log
import json

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


def get_callbacks():
    callbacks = getattr(g, '_database', None)
    if callbacks is None:
        callbacks = {}
        g._database = callbacks
    return callbacks


def attach_buttons(result, callback_id):
    result["attachments"] = [
        {
            "callback_id": callback_id,
            "actions": [
                {
                    "name": "Send",
                    "text": "send",
                    "type": "button",
                    "value": "chess",
                    "style": "primary"
                },
                {
                    "name": "Shuffle",
                    "text": "shuffle",
                    "type": "button",
                    "value": "chess"
                },
                {
                    "name": "Avbryt",
                    "text": "avbryt",
                    "value": "chess",
                    "style": "danger"
                },
            ]
        }
    ]


@app.route('/')
def hello_world() -> str:
    return "home"


def interactive(data, trigger_id):
    prev_request_data = get_callbacks()[trigger_id]
    if data["actions"][0]["value"] == "send":
        result = prev_request_data["result"]
        result["response_type"] = "in_channel"
        # todo somehow delete buttons
        return Response(
            response=json.dumps(result),
            status=200,
            mimetype='application/json'
        )
    elif data["actions"][0]["value"] == "shuffle":
        command_str = prev_request_data["command_str"]
        args = prev_request_data["args"]
        return command_str, args
    elif data["actions"][0]["value"] == "avbryt":
        return Response(
            status=200,
            mimetype='application/json'
        )


@app.route('/slash_cmds', methods=['POST'])
def slash_cmds():
    log.info("incoming request")
    data = request.form

    if not data.get('token') == config.v2_verification_token:
        return

    trigger_id = data["trigger_id"]

    if data.get('type') == "interactive_message":
        log.info("request is interactive")
        r = interactive(data, trigger_id)
        if isinstance(r, Response):
            return Response
        else:
            command_str, args = r
    else:
        command_str = data["command"][1:]
        args = data['text']
    log.info(f"command: {command_str}")
    log.info(f"args: {args}")
    log.info(f"trigger_id: {trigger_id}")

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
    attach_buttons(result, callback_id=trigger_id)

    request_data = {
        "result": result,
        "command_str": command_str,
        "args": args,
    }
    get_callbacks()[trigger_id] = request_data

    log.info(f"result: {result}")

    return Response(
        response=json.dumps(result),
        status=200,
        mimetype='application/json'
    )


def setup():
    quotes_db = quotes.Quotes(db=get_db())
    commands.command_switch["msn"].keywords["quotes_db"] = quotes_db
    commands.command_switch["quote"].keywords["quotes_db"] = quotes_db

    drop_pics = droppics.DropPics(db=get_db())
    drop_pics.connect_dbx()
    commands.command_switch["pic"].keywords["drop_pics"] = drop_pics


def main():
    setup()
    log.info("GargBot 3000 server operational!")
    # app.run() uwsgi does this
    pass


if __name__ == '__main__':
    main()
