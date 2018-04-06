#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

import time
import sys
import datetime as dt
import threading
import itertools

from gargbot_3000 import config
from gargbot_3000 import congrats
from gargbot_3000 import commands
from gargbot_3000 import database_manager
from gargbot_3000 import quotes
from gargbot_3000 import droppics

import MySQLdb
from slackclient import SlackClient
import websocket

from typing import Tuple, Dict
from MySQLdb.connections import Connection


def wait_for_slack_output(slack_client: SlackClient) -> Tuple[str, str, str]:
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
        except websocket.WebSocketConnectionClosedException:
            slack_client.rtm_connect()
            continue
        if not (output_list or len(output_list) > 0):
            continue
        try:
            bot_msg = next(
                output for output in output_list
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


def send_response(slack_client: SlackClient, response: Dict, channel: str):
    log.info(dt.datetime.now())
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def handle_congrats(db_connection, slack_client: SlackClient, drop_pics):
    birthdays = congrats.get_birthdays()
    for birthday in itertools.cycle(birthdays):
        log.info(f"Next birthday: {birthday.nick}, at {birthday.next_bday}")
        time.sleep(birthday.seconds_to_bday())
        response = congrats.get_greeting(birthday, db_connection, drop_pics)

        send_response(slack_client, response=response, channel=config.main_channel)


def setup() -> Tuple[SlackClient, Connection]:
    db_connection = database_manager.connect_to_database()
    commands.command_switch["msn"].keywords["db"] = db_connection
    commands.command_switch["quote"].keywords["db"] = db_connection
    commands.command_switch["pic"].keywords["db"] = db_connection

    quotes_db = quotes.Quotes(db=db_connection)
    commands.command_switch["msn"].keywords["quotes_db"] = quotes_db
    commands.command_switch["quote"].keywords["quotes_db"] = quotes_db

    drop_pics = droppics.DropPics(db=db_connection)
    drop_pics.connect_dbx()
    commands.command_switch["pic"].keywords["drop_pics"] = drop_pics

    slack_client = SlackClient(config.slack_bot_user_token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    congrats_thread = threading.Thread(
        target=handle_congrats,
        args=(db_connection, slack_client, drop_pics)
    )
    congrats_thread.daemon = True
    congrats_thread.start()

    return slack_client, db_connection


def main():
    slack_client, db_connection = setup()

    log.info("GargBot 3000 task operational!")

    try:
        while True:
            time.sleep(1)
            text, channel, user = wait_for_slack_output(slack_client)

            try:
                command_str, *args = text.split()
            except ValueError:
                command_str = ""
                args = None

            command_str = command_str.lower()
            log.info(f"command: {command_str}")
            log.info(f"args: {args}")

            try:
                command_function = commands.command_switch[command_str]
            except KeyError:
                command_function = commands.cmd_not_found
                args = [command_str]

            response = commands.try_or_panic(command_function, args)

            if response is None:
                continue

            send_response(slack_client, response, channel)

    except KeyboardInterrupt:
        sys.exit()
    finally:
        db_connection.close()


if __name__ == '__main__':
    main()
