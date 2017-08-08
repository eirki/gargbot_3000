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
import droppics
import quotes
import congrats


def command_handler_wrapper(quotes_db, drop_pics):
    def cmd_ping():
        """if command is 'ping' """
        response = {"text": "GargBot 3000 is active. Beep boop beep"}
        return response

    def cmd_pic(*args):
        """if command is 'pic'"""
        text = {}
        if args:
            picurl, timestamp, pic_random = drop_pics.get_pic(*args)
            if pic_random:
                text = {"text": f"Fant ikke bilde med {args}'. Her er et tilfeldig bilde i stedet:"}
        else:
            picurl, timestamp, _ = drop_pics.get_pic()

        response = {"attachments": [{"fallback":  picurl,
                                     "image_url": picurl,
                                     "ts": timestamp,
                                     **text}]}
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
        f"Beep boop beep! Nôt sure whåt you mean by {command}. Dette er kommandoene jeg skjønner:\n"
        "`@gargbot_3000 pic [lark/fe/skating/henging] [gargling] [år]`: viser random bilde\n"
        "`@gargbot_3000 quote [garling]`: henter tilfedlig sitat fra forumet\n"
        "`@gargbot_3000 vidoi`: viser tilfedlig musikkvideo fra muzakvidois tråden på forumet\n"
        "`@gargbot_3000 /random`: viser tilfedlig bilde fra \\random tråden på forumet\n"
        "`@gargbot_3000 Hvem [spørsmål]`: svarer på spørsmål om garglings \n"
        "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
    )
    response = {"text": text}
    return response


def cmd_panic(exc):
    text = (
        f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
        " med systemadministrator ummidelbart, før det er for sent. "
        "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    )
    response = {"text": text}
    return response


def filter_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    AT_BOT = f"<@{config.bot_id}>"
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and "text" in output and AT_BOT in output["text"]:
                return (output["text"].replace(AT_BOT, "").strip().lower(),
                        output["channel"], output["user"])
    return None, None, None


def send_response(slack_client, response, channel):
    log.info(dt.datetime.now())
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def handle_congrats(slack_client):
    channel = "C335L1LMN"
    birthdays = congrats.get_birthdays()
    for birthday in itertools.cycle(birthdays):
        log.info(f"Next birthday: {birthday.nick}, at {birthday.next_bday}")
        time.sleep(birthday.seconds_to_bday())
        text = congrats.get_greeting(birthday)
        picurl = "https://pbs.twimg.com/media/DAgm_X3WsAAQRGo.jpg"
        response = {"text": text, "attachments": [{"fallback":  picurl, "image_url": picurl}]}
        send_response(slack_client, response=response, channel=channel)


def main():
    db_connection = config.connect_to_database()

    quotes_db = quotes.Quotes(db=db_connection)

    drop_pics = droppics.DropPics(db=db_connection)
    drop_pics.connect_dbx()

    slack_client = SlackClient(config.slack_token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    command_switch = command_handler_wrapper(quotes_db, drop_pics)

    congrats_thread = threading.Thread(target=handle_congrats, args=(slack_client,))
    congrats_thread.daemon = True
    congrats_thread.start()

    log.info("GargBot 3000 is operational!")
    try:
        while True:
            time.sleep(1)
            try:
                text, channel, user = filter_slack_output(slack_client.rtm_read())
            except websocket.WebSocketConnectionClosedException:
                slack_client.rtm_connect()
                continue

            if not (text and channel):
                continue

            command, *args = text.split()
            log.info(f"command: {command}")
            log.info(f"args: {args}")

            try:
                command_function = command_switch[command]
            except KeyError:
                command_function = cmd_not_found
                args = [command]

            try:
                response = command_function(*args)
            except MySQLdb.OperationalError:
                db_connection = config.connect_to_database()
                quotes_db.db = db_connection
                drop_pics.db = db_connection
                response = command_function(*args)
            except Exception as exc:
                log.error(traceback.format_exc())
                response = cmd_panic(exc)

            send_response(slack_client, response, channel)

    except KeyboardInterrupt:
        sys.exit()
    finally:
        db_connection.close()


if __name__ == "__main__":
    main()
