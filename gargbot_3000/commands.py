#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

import datetime as dt
import random
from functools import partial
import traceback

from slackclient import SlackClient
import MySQLdb

from gargbot_3000 import config
from gargbot_3000 import droppics

from MySQLdb.connections import Connection
from typing import Dict, List, Optional, Any

command_explanation = (
    "`@gargbot_3000 pic [lark/fe/skating/henging] [gargling] [år]`: viser random bilde\n"
    "`@gargbot_3000 quote [garling]`: henter tilfeldig sitat fra forumet\n"
    "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
    "`@gargbot_3000 Hvem [spørsmål]`: svarer på spørsmål om garglings \n"
)


def cmd_ping() -> Dict:
    """if command is 'ping' """
    response = {"text": "GargBot 3000 is active. Beep boop beep"}
    return response


def cmd_welcome() -> Dict:
    """when joining new channel"""
    text = (
        "Hei hei kjære alle sammen!\n"
        "Dette er kommandoene jeg skjønner:\n"
        + command_explanation
    )
    response = {"text": text}
    return response


def cmd_pic(db: Connection, drop_pics: droppics.DropPics, args: Optional[List[str]]=None) -> Dict:
    """if command is 'pic'"""
    picurl, timestamp, error_text = drop_pics.get_pic(db, args)
    response = {"attachments": [{"fallback":  picurl,
                                 "image_url": picurl,
                                 "ts": timestamp}]}
    if error_text:
        response["text"] = error_text

    return response


def cmd_quote(db: Connection, quotes_db, args: Optional[List[str]]=None) -> Dict:
    """if command is 'quote'"""
    text = quotes_db.garg(db, "quote", args)
    response = {"text": text}
    return response


def cmd_msn(db: Connection, quotes_db, args: Optional[List[str]]=None) -> Dict:
    """if command is 'msn'"""
    date, text = quotes_db.msn(db, args)

    response = {"attachments":
                [{"author_name": f"{msg_user}:",
                  "text": msg_text,
                  "color": msg_color}
                 for msg_user, msg_text, msg_color in text]
                }
    response["attachments"][0]["pretext"] = date
    return response


def cmd_hvem(args) -> Dict:
    """if command.lower().startswith("hvem")"""
    user = random.choice(config.gargling_names)
    answ = " ".join(args).replace("?", "!")
    text = f"{user} {answ}"
    response = {"text": text}
    return response


def cmd_not_found(args: str) -> Dict:
    text = (
        f"Beep boop beep! Nôt sure whåt you mean by `{args}`. "
        "Dette er kommandoene jeg skjønner:\n"
        + command_explanation
    )
    response = {"text": text}
    return response


def cmd_panic(exc) -> Dict:
    text = (
        f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
        " med systemadministrator umiddelbart, før det er for sent. "
        "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    )
    response = {"text": text}
    return response


def send_response(slack_client: SlackClient, response: Dict, channel: str):
    log.info(dt.datetime.now())
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def try_or_panic(command_function, args):
    try:
        response = command_function(args=args) if args else command_function()
    except MySQLdb.OperationalError as op_exc:
        db_connection = command_function.keywords["db"]
        try:
            db_connection.ping()
        except MySQLdb.OperationalError:
            log.info("Database disconnected. Trying to reconnect")
            db_connection.ping(True)
            response = command_function(args=args) if args else command_function()
        else:
            # OperationalError not caused by connection issue. Reraise error to log below
            raise op_exc
    except Exception as exc:
        log.error(traceback.format_exc())
        response = cmd_panic(exc)
    return response


command_switch = {
    "ping": partial(cmd_ping),
    "new_channel": partial(cmd_welcome),
    "hvem": partial(cmd_hvem),
    "pic": partial(cmd_pic),
    "quote": partial(cmd_quote),
    "msn": partial(cmd_msn),
    }

