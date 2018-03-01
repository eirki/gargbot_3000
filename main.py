#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import datetime as dt
import time
import traceback
import sys
import random
import threading
import itertools

import MySQLdb
from slackclient import SlackClient
import websocket

import config
import database_manager
import droppics
import quotes
import congrats
import games


command_explanation = (
    "`@gargbot_3000 games`: viser liste over spillnight-spill\n"
    "`@gargbot_3000 pic [lark/fe/skating/henging] [gargling] [år]`: viser random bilde\n"
    "`@gargbot_3000 quote [garling]`: henter tilfeldig sitat fra forumet\n"
    "`@gargbot_3000 vidoi`: viser tilfeldig musikkvideo fra muzakvidois tråden på forumet\n"
    "`@gargbot_3000 /random`: viser tilfeldig bilde fra \\random tråden på forumet\n"
    "`@gargbot_3000 Hvem [spørsmål]`: svarer på spørsmål om garglings \n"
    "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
)


def command_handler_wrapper(quotes_db, drop_pics, games_db):
    def cmd_ping():
        """if command is 'ping' """
        response = {"text": "GargBot 3000 is active. Beep boop beep"}
        return response

    def cmd_welcome():
        """when joining new channel"""
        text = (
            "Hei hei kjære alle sammen!\n"
            "Dette er kommandoene jeg skjønner:\n"
            + command_explanation
        )
        response = {"text": text}
        return response

    def cmd_games(user, *args):
        """if command is 'game'"""
        output = games_db.main(user, *args)
        if output is None:
            return
        elif isinstance(output, str):
            response = {"text": output}
        else:
            response = {"text": games.command_explanation,
                        "attachments":
                        [{"title": (":star2: " * stars) + name,
                          "text": f"Votes: {votes}. (Game #{game_number})"}
                         for game_number, name, votes, stars in output]
                        }
            return response
        return response

    def cmd_pic(*args):
        """if command is 'pic'"""
        picurl, timestamp, error_text = drop_pics.get_pic(*args)
        response = {"attachments": [{"fallback":  picurl,
                                     "image_url": picurl,
                                     "ts": timestamp}]}
        if error_text:
            response["text"] = error_text

        return response

    def cmd_quote(*user):
        """if command is 'quote'"""
        if user:
            response = {"text": quotes_db.garg("quote", *user)}
        else:
            response = {"text": quotes_db.garg("quote")}
        return response

    def cmd_random():
        """if command is '/random'"""
        response = {"attachments": [{"fallback":  quotes_db.garg("random"),
                                     "image_url": quotes_db.garg("random")}]}
        return response

    def cmd_vidoi():
        """if command is 'vidoi'"""
        response = {"text": quotes_db.garg("vidoi")}
        return response

    def cmd_msn(*user):
        """if command is 'msn'"""
        if user:
            date, text = quotes_db.msn(*user)
        else:
            date, text = quotes_db.msn()

        response = {"attachments":
                    [{"author_name": f"{msg_user}:",
                      "text": msg_text,
                      "color": msg_color}
                     for msg_user, msg_text, msg_color in text]
                    }
        response["attachments"][0]["pretext"] = date
        return response

    def cmd_hvem(*qtn):
        """if command.lower().startswith("hvem")"""
        user = random.choice(config.gargling_names)
        answ = " ".join(qtn).replace("?", "!")
        text = f"{user} {answ}"
        response = {"text": text}
        return response

    switch = {
        "ping": cmd_ping,
        "new_channel": cmd_welcome,
        "games": cmd_games,
        "pic": cmd_pic,
        "quote": cmd_quote,
        "/random": cmd_random,
        "vidoi": cmd_vidoi,
        "msn": cmd_msn,
        "hvem": cmd_hvem,
        }
    return switch


def cmd_not_found(command):
    text = (
        f"Beep boop beep! Nôt sure whåt you mean by `{command}`. "
        "Dette er kommandoene jeg skjønner:\n"
        + command_explanation
    )
    response = {"text": text}
    return response


def cmd_panic(exc):
    text = (
        f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
        " med systemadministrator umiddelbart, før det er for sent. "
        "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    )
    response = {"text": text}
    return response


def wait_for_slack_output(slack_client):
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


def send_response(slack_client, response, channel):
    log.info(dt.datetime.now())
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def handle_congrats(slack_client, drop_pics):
    birthdays = congrats.get_birthdays()
    for birthday in itertools.cycle(birthdays):
        log.info(f"Next birthday: {birthday.nick}, at {birthday.next_bday}")
        time.sleep(birthday.seconds_to_bday())
        response = congrats.get_greeting(birthday, drop_pics)

        send_response(slack_client, response=response, channel=config.main_channel)


def setup():
    db_connection = database_manager.connect_to_database()

    quotes_db = quotes.Quotes(db=db_connection)

    drop_pics = droppics.DropPics(db=db_connection)
    drop_pics.connect_dbx()

    games_db = games.Games(db=db_connection)

    slack_client = SlackClient(config.slack_token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    command_switch = command_handler_wrapper(quotes_db, drop_pics, games_db)

    congrats_thread = threading.Thread(
        target=handle_congrats,
        args=(slack_client, drop_pics)
    )
    congrats_thread.daemon = True
    congrats_thread.start()

    return slack_client, command_switch, db_connection


def main():
    slack_client, command_switch, db_connection = setup()
    log.info("GargBot 3000 is operational!")

    try:
        while True:
            time.sleep(1)
            text, channel, user = wait_for_slack_output(slack_client)

            command_str, *args = text.split()
            command_str = command_str.lower()
            log.info(f"command: {command_str}")
            if command_str == "games":
                args.insert(0, user)
            log.info(f"args: {args}")

            try:
                command_function = command_switch[command_str]
            except KeyError:
                command_function = cmd_not_found
                args = [command_str]

            try:
                response = command_function(*args)
            except MySQLdb.OperationalError as op_exc:
                try:
                    db_connection.ping()
                except MySQLdb.OperationalError:
                    log.info("Database disconnected. Trying to reconnect")
                    db_connection.ping(True)
                    response = command_function(*args)
                else:
                    # OperationalError not caused by connection issue. Reraise error to log below
                    raise op_exc
            except Exception as exc:
                log.error(traceback.format_exc())
                response = cmd_panic(exc)

            if response is None:
                continue

            send_response(slack_client, response, channel)

    except KeyboardInterrupt:
        sys.exit()
    finally:
        db_connection.close()


if __name__ == "__main__":
    main()
