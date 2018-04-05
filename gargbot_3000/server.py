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


@app.route('/')
def hello_world() -> str:
    return "home"


@app.route('/slash_cmds')
def slash_cmds():
    if not request.form.get('token') == config.v2_verification_token:
        return

    data = request.form
    command_str = data["command"][1:]
    args = data['text']
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

    response = Response(
        response=json.dumps(result),
        status=200,
        mimetype='application/json'
    )

    return response


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
