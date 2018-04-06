#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log
import json

import requests
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
                "name": "share",
                "text": "Del i kanal",
                "type": "button",
                "style": "primary",
                "value": json.dumps({"original_response": result})
            },
            {
                "name": "shuffle",
                "text": "Shuffle",
                "type": "button",
                "value": json.dumps({"original_func": func, "original_args": args})
            },
            {
                "name": "cancel",
                "text": "Avbryt",
                "value": "avbryt",
                "type": "button",
                "style": "danger"
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


@app.route('/')
def hello_world() -> str:
    return "home"


@app.route('/interactive', methods=['POST'])
def interactive():
    log.info("incoming interactive request:")
    data = json.loads(request.form['payload'])
    log.info(data)
    if not data.get('token') == config.slack_verification_token:
        return Response(status=403)
    action = data["actions"][0]["name"]

    if action == "share":
        log.info("Interactive: share")
        response_url = data["response_url"]
        delete_original = {
            "response_type": "ephemeral",
            "replace_original": True,
            "text": "Sharing is caring!"
        }
        r = requests.post(response_url, json=delete_original)
        log.info(r.text)

        result = json.loads(data["actions"][0]["value"])["original_response"]
        result['replace_original'] = False
        result["response_type"] = "in_channel"

    elif action == "cancel":
        log.info("Interactive: cancel")
        result = {
            "response_type": "ephemeral",
            "replace_original": True,
            "text": "Canceled! Går fint det. Ikke noe problem for meg. Hadde ikke lyst uansett."
        }

    elif action == "shuffle":
        log.info("Interactive: shuffle")
        command_str = json.loads(data["actions"][0]["value"])["original_func"]
        args = json.loads(data["actions"][0]["value"])["original_args"]
        callback_id = data["callback_id"]
        result = get_and_execute_command(command_str, args, callback_id)
        result["replace_original"] = True

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

    if not data.get('token') == config.slack_verification_token:
        return Response(status=403)

    command_str = data["command"][1:]
    args = data['text']
    args = args.replace("@", "").split()

    trigger_id = data["trigger_id"]

    result = get_and_execute_command(command_str, args, trigger_id)

    log.info(f"result: {result}")
    return Response(
        response=json.dumps(result),
        status=200,
        mimetype='application/json'
    )


def get_and_execute_command(command_str, args, callback_id):
    log.info(f"command: {command_str}")
    log.info(f"args: {args}")

    try:
        command_function = commands.command_switch[command_str]
    except KeyError:
        command_function = commands.cmd_not_found
        args = [command_str]

    if command_str in commands.commands_using_db:
        db_connection = get_db()
        command_function.keywords["db"] = db_connection

    result = commands.try_or_panic(command_function, args)
    error = result.get("text", "").startswith("Error")
    if command_str in {"ping", "hvem"} and error is False:
        result["response_type"] = "in_channel"
    elif error is False:
        result = attach_buttons(
            callback_id=callback_id,
            result=result,
            func=command_str,
            args=args
        )
    return result


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
