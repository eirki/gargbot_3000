#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

# Core
import datetime as dt
from functools import partial

# Dependencies
from slackclient import SlackClient
import MySQLdb
from requests.exceptions import SSLError

# Internal
import database_manager
import droppics
import quotes

# Typing
from MySQLdb.connections import Connection
from typing import Dict, List, Optional

command_explanation = (
    "`@gargbot_3000 Hvem [spørsmål]`: svarer på spørsmål om garglings \n"
    "`@gargbot_3000 pic [lark/fe/skating/henging] [gargling] [år]`: viser random bilde\n"
    "`@gargbot_3000 quote [garling]`: henter tilfeldig sitat fra forumet\n"
    "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
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


def cmd_hvem(args: List[Optional[str]], db: Connection) -> Dict:
    """if command.lower().startswith("hvem")"""
    with db as cursor:
        sql = "SELECT first_name FROM user_ids ORDER BY RAND() LIMIT 1"
        cursor.execute(sql)
        data = cursor.fetchone()
        user = data["first_name"]
    answ = " ".join(args).replace("?", "!")
    text = f"{user} {answ}"
    response = {"text": text}
    return response


def cmd_pic(args: List[Optional[str]], db: Connection, drop_pics: droppics.DropPics) -> Dict:
    """if command is 'pic'"""
    picurl, timestamp, error_text = drop_pics.get_pic(db, args)
    response = {"attachments": [{"fallback":  picurl,
                                 "image_url": picurl,
                                 "ts": timestamp}]}
    if error_text:
        response["text"] = error_text

    return response


def cmd_quote(args: List[Optional[str]], db: Connection, quotes_db: quotes.Quotes) -> Dict:
    """if command is 'quote'"""
    text = quotes_db.garg(db, args)
    response = {"text": text}
    return response


def cmd_msn(args: List[Optional[str]], db: Connection, quotes_db: quotes.Quotes) -> Dict:
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


def cmd_not_found(args: str) -> Dict:
    text = (
        f"Beep boop beep! Nôt sure whåt you mean by `{args}`. "
        "Dette er kommandoene jeg skjønner:\n"
        + command_explanation
    )
    response = {"text": text}
    return response


def cmd_panic(exc: Exception) -> Dict:
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


def execute(
        command_str: str,
        args: List,
        db_connection: Connection,
        drop_pics: droppics.DropPics,
        quotes_db: quotes.Quotes,
        ) -> Dict:
    log.info(f"command: {command_str}")
    log.info(f"args: {args}")

    switch = {
        "ping": cmd_ping,
        "new_channel": cmd_welcome,
        "hvem": partial(cmd_hvem, args, db=db_connection),
        "pic": partial(cmd_pic, args, db=db_connection, drop_pics=drop_pics),
        "quote": partial(cmd_quote, args, db=db_connection, quotes_db=quotes_db),
        "msn": partial(cmd_msn, args, db=db_connection, quotes_db=quotes_db),
    }
    try:
        command_func = switch[command_str]
    except KeyError:
        command_func = partial(cmd_not_found, command_str)

    try:
        return command_func()
    except MySQLdb.OperationalError as op_exc:
        database_manager.reconnect_if_disconnected(db_connection)
        try:
            return command_func()
        except Exception as exc:
            # OperationalError not caused by connection issue.
            log.error("Error in command execution", exc_info=True)
            return cmd_panic(exc)
    except SSLError as ssl_exc:
        # Dropbox sometimes gives SSLerrors, try again:
        try:
            return command_func()
        except Exception as exc:
            # SSLError fixed on retry. Reraise error to log below
            log.error("Error in command execution", exc_info=True)
            return cmd_panic(exc)
    except Exception as exc:
        log.error("Error in command execution", exc_info=True)
        return cmd_panic(exc)
