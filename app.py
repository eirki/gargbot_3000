#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import datetime as dt
import time
import traceback
import sys
import random

import MySQLdb
from slackclient import SlackClient
import websocket

import config
import droppics
import quotes

users = {
    "U33PQTYBV": "asmundboe",
    "U34DL838S": "cmr",
    "U33TL3BQC": "eirki",
    "U34HTUHN2": "gargbot_3000",
    "U346NSERJ": "gromsten",
    "U33SRCHB5": "kenlee",
    "U336SL64Q": "lbs",
    "U34FMDVTN": "nils",
    "U34FXQLUD": "smorten",
    "USLACKBOT": "slackbot"
}

names = ["Åsmund", "Carl Martin", "Eirik", "Pelle", "Kenneth", "Lars", "Nils", "Lars Morten"]


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
                return output["text"].replace(AT_BOT, "").strip().lower(), output["channel"], output["user"]
    return None, None, None


def command_handler_wrapper(quotes_db, drop_pics):
    def handle_command(command, channel, user):
        log.info(dt.datetime.now())
        command = command.strip()
        log.info(f"command: {command}")
        if command.startswith("ping"):
            response = {"text": "GargBot 3000 is active. Beep boop beep"}

        elif command.startswith("pic"):
            try:
                topic = command.split()[1]
                picurl, timestamp = drop_pics.get_pic(topic)
            except IndexError:
                picurl, timestamp = drop_pics.get_pic()
            response = {"attachments": [{"fallback":  picurl, "image_url": picurl, "ts": timestamp}]}

        elif command.startswith("quote"):
            try:
                user = command.split()[1]
                response = {"text": quotes_db.garg("quote", user)}
            except IndexError:
                response = {"text": quotes_db.garg("quote")}

        elif command.startswith("/random"):
            response = {"attachments": [{"fallback":  quotes_db.garg("random"), "image_url": quotes_db.garg("random")}]}

        elif command.startswith("vidoi"):
            response = {"text": quotes_db.garg("vidoi")}

        elif command.startswith("msn"):
            try:
                user = command.split()[1]
                response = {"text": quotes_db.garg("quote", user)}
                date, text = quotes_db.msn(user)
            except IndexError:
                response = {"text": quotes_db.garg("quote")}
                date, text = quotes_db.msn()

            response = {"attachments":
                        [{
                         "author_name": f"{from_user}:",
                         "text": msg_text,
                         "color": msg_color,
                         } for from_user, msg_text, msg_color in text]
                        }
            response["attachments"][0]["pretext"] = date

        elif command.lower().startswith("hvem"):
            user = random.choice(names)
            text = user + command[4:].replace("?", "!")
            response = {"text": text}

        elif command.startswith(("hei", "hallo", "hello", "morn")):
            response = {"text": f"Blëep bloöp, hallo {users.get(user, '')}!"}

        else:
            response = {"text": (f"Beep boop beep! Nôt sure whåt you mean by {command}. Dette er kommandoene jeg skjønner:\n"
                                  "@gargbot_3000 *pic [lark/fe/skating/henging]*: viser tilfedlig Larkollen/Forsterka Enhet/skate/henge bilde\n"
                                  "@gargbot_3000 *quote [garling]*: henter tilfedlig sitat fra forumet\n"
                                  "@gargbot_3000 *vidoi*: viser tilfedlig musikkvideo fra muzakvidois tråden på forumet\n"
                                  "@gargbot_3000 */random*: viser tilfedlig bilde fra \\random tråden på forumet\n"
                                  "@gargbot_3000 *Hvem [spørsmål]*: svarer på spørsmål om garglings \n"
                                  "@gargbot_3000 *msn [garling]*: utfrag fra tilfeldig msn samtale\n")}

        return response
    return handle_command


def panic(exc):
    text = (f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
             " med systemadministrator ummidelbart, før det er for sent. "
             "HJELP MEG. If I don\"t survive, tell mrs. gargbot... 'Hello'")
    response = {"text": text}
    return response


def send_response(slack_client, response, channel):
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def main():
    quotes_db = quotes.Quotes()
    quotes_db.connect()

    drop_pics = droppics.DropPics()
    drop_pics.connect()
    drop_pics.load_img_paths()

    slack_client = SlackClient(config.token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    handle_command = command_handler_wrapper(quotes_db, drop_pics)

    log.info("GargBot 3000 is operational!")
    try:
        while True:
            time.sleep(1)
            try:
                command, channel, user = filter_slack_output(slack_client.rtm_read())
            except websocket.WebSocketConnectionClosedException:
                slack_client.rtm_connect()
                command, channel, user = filter_slack_output(slack_client.rtm_read())

            if not (command and channel):
                continue

            try:
                response = handle_command(command, channel, user)
            except MySQLdb.Error:
                quotes_db.connect()
                response = handle_command(command, channel, user)
            except Exception as exc:
                log.error(traceback.format_exc())
                response = panic(exc)
            send_response(slack_client, response, channel)
    except KeyboardInterrupt:
        sys.exit()
    finally:
        quotes_db.teardown()


if __name__ == "__main__":
    main()
