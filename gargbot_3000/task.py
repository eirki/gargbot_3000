#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

# Core
import time
import sys
import datetime as dt
import threading
import itertools

# Dependencies
from slackclient import SlackClient
import websocket

# Internal
from gargbot_3000 import config
from gargbot_3000 import congrats
from gargbot_3000 import commands
from gargbot_3000 import database_manager
from gargbot_3000 import quotes
from gargbot_3000 import droppics


# Typing
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
    birthdays = congrats.get_birthdays(db_connection)
    for birthday in itertools.cycle(birthdays):
        log.info(f"Next birthday: {birthday.nick}, at {birthday.next_bday}")
        try:
            time.sleep(birthday.seconds_to_bday())
            response = congrats.get_greeting(birthday, db_connection, drop_pics)
            send_response(slack_client, response=response, channel=config.main_channel)
        except OverflowError:
            log.info(f"Too long sleep length for OS. Restart before next birthday, at {birthday.next_bday}")
            break


def setup() -> Tuple[SlackClient, Connection, droppics.DropPics, quotes.Quotes]:
    db_connection = database_manager.connect_to_database()

    drop_pics = droppics.DropPics(db=db_connection)

    quotes_db = quotes.Quotes(db=db_connection)
    # commands.command_switch["msn"].keywords["quotes_db"] = quotes_db
    # commands.command_switch["quote"].keywords["quotes_db"] = quotes_db

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

    return slack_client, db_connection, drop_pics, quotes_db


def main():
    slack_client, db_connection, drop_pics, quotes_db = setup()

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

            response = commands.execute(
                command_str=command_str,
                args=args,
                db_connection=db_connection,
                drop_pics=drop_pics,
                quotes_db=quotes_db,
            )

            send_response(slack_client, response, channel)

    except KeyboardInterrupt:
        sys.exit()
    finally:
        db_connection.close()


if __name__ == '__main__':
    main()
