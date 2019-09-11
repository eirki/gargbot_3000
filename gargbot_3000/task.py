#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import sys
import time
import typing as t
from functools import partial

import psycopg2
import websocket
from psycopg2.extensions import connection
from slackclient import SlackClient
from slackclient.server import SlackConnectionError

from gargbot_3000 import commands, config, database_manager, droppics, quotes
from gargbot_3000.logger import log


def wait_for_slack_output(slack_client: SlackClient) -> t.Tuple[str, str, str]:
    """
        The Slack Real Time Messaging API is an events firehose.
        This parsing function returns when a message is
        directed at the Bot, based on its ID.
    """
    AT_BOT = f"<@{config.bot_id}>"
    while True:
        time.sleep(1)
        try:
            output_list = slack_client.rtm_read()
        except (
            websocket.WebSocketConnectionClosedException,
            SlackConnectionError,
            TimeoutError,
        ):
            slack_client.rtm_connect()
            continue
        if not (output_list or len(output_list) > 0):
            continue
        try:
            bot_msg = next(
                output
                for output in output_list
                if output and "text" in output and AT_BOT in output["text"]
            )
        except StopIteration:
            continue

        text = bot_msg["text"].replace(AT_BOT, "").strip()
        if "has joined the " in text:
            text = "new_channel"
        channel = bot_msg["channel"]
        user = bot_msg["user"]
        return text, channel, user


def send_response(slack_client: SlackClient, response: t.Dict, channel: str):
    log.info(dt.datetime.now())
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def setup() -> t.Tuple[SlackClient, droppics.DropPics, quotes.Quotes, connection]:
    db_connection = database_manager.connect_to_database()

    drop_pics = droppics.DropPics(db=db_connection)

    quotes_db = quotes.Quotes(db=db_connection)

    slack_client = SlackClient(config.slack_bot_user_token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    return slack_client, drop_pics, quotes_db, db_connection


def main():
    slack_client, drop_pics, quotes_db, db_connection = setup()

    log.info("GargBot 3000 task operational!")
    try:
        while True:
            time.sleep(1)
            text, channel, user = wait_for_slack_output(slack_client)

            try:
                command_str, *args = text.split()
            except ValueError:
                command_str = ""
                args = []
            command_str = command_str.lower()
            command_func = partial(
                commands.execute,
                command_str=command_str,
                args=args,
                db_connection=db_connection,
                drop_pics=drop_pics,
                quotes_db=quotes_db,
            )
            try:
                response = command_func()
            except psycopg2.OperationalError:
                db_connection = database_manager.connect_to_database()
                try:
                    response = command_func()
                except Exception as exc:
                    # OperationalError not caused by connection issue.
                    log.error("Error in command execution", exc_info=True)
                    response = commands.cmd_panic(exc)

            send_response(slack_client, response, channel)

    except KeyboardInterrupt:
        sys.exit()
    finally:
        database_manager.close_database_connection(db_connection)
