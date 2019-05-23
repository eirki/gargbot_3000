#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import time
import typing as t
from functools import partial

import dropbox
import psycopg2
from psycopg2.extensions import connection
from requests.exceptions import SSLError

from gargbot_3000 import droppics, quotes
from gargbot_3000.logger import log


def prettify_date(date: dt.datetime) -> str:
    timestamp = int(time.mktime(date.timetuple()))
    return (
        f"<!date^{timestamp}^{{date_pretty}} "
        f"at {date.strftime('%H:%M')}| "
        f"{date.strftime('%A %d. %B %Y %H:%M')}>"
    )


def command_explanation(server: bool = False):
    commands = (
        "`@gargbot_3000 hvem [spørsmål]`: svarer på spørsmål om garglings \n"
        "`@gargbot_3000 pic [lark/fe/skating/henging] [gargling] [år]`: random bilde\n"
        "`@gargbot_3000 forum [garling]`: henter tilfeldig sitat fra ye olde forumet\n"
        "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
    )
    return commands if server is False else commands.replace("@gargbot_3000 ", "/")


def cmd_ping() -> t.Dict:
    """if command is 'ping' """
    text = "GargBot 3000 is active. Beep boop beep"
    response: t.Dict[str, t.Any] = {"text": text}
    return response


def cmd_welcome() -> t.Dict:
    """when joining new channel"""
    text = (
        "Hei hei kjære alle sammen!\n"
        "Dette er kommandoene jeg skjønner:\n" + command_explanation()
    )
    response: t.Dict[str, t.Any] = {"text": text}
    return response


def cmd_server_explanation() -> t.Dict:
    expl = command_explanation(server=True)
    text = "Beep boop beep! Dette er kommandoene jeg skjønner:\n" + expl
    response: t.Dict[str, t.Any] = {"text": text}
    return response


def cmd_hvem(args: t.List[str], db: connection) -> t.Dict:
    """if command.lower().startswith("hvem")"""
    with db.cursor() as cursor:
        sql = "SELECT first_name FROM user_ids ORDER BY RANDOM() LIMIT 1"
        cursor.execute(sql)
        data = cursor.fetchone()
        user = data["first_name"]
    answ = " ".join(args).replace("?", "!")
    text = f"{user} {answ}"
    response: t.Dict[str, t.Any] = {"text": text}
    return response


def cmd_pic(
    args: t.Optional[t.List[str]], db: connection, drop_pics: droppics.DropPics
) -> t.Dict:
    """if command is 'pic'"""
    picurl, date, description = drop_pics.get_pic(db, args)
    pretty_date = prettify_date(date)
    blocks = []
    image_block = {"type": "image", "image_url": picurl, "alt_text": picurl}
    blocks.append(image_block)
    context_block: t.Dict[str, t.Any] = {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": pretty_date}],
    }
    blocks.append(context_block)
    if description:
        description_block: t.Dict[str, t.Any] = {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": description}],
        }
        blocks.append(description_block)
    response = {"text": picurl, "blocks": blocks}

    return response


def cmd_forum(
    args: t.Optional[t.List[str]], db: connection, quotes_db: quotes.Quotes
) -> t.Dict:
    """if command is 'forum'"""
    text, user, avatar_url, date, url, description = quotes_db.forum(db, args)
    pretty_date = prettify_date(date)
    text_block = {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    context_block = {
        "type": "context",
        "elements": [
            {"type": "image", "image_url": avatar_url, "alt_text": user},
            {"type": "plain_text", "text": user},
            {"type": "mrkdwn", "text": pretty_date},
            {"type": "mrkdwn", "text": url},
            {"type": "mrkdwn", "text": description},
        ],
    }
    response = {"text": text, "blocks": [text_block, context_block]}

    return response


def cmd_msn(
    args: t.Optional[t.List[str]], db: connection, quotes_db: quotes.Quotes
) -> t.Dict:
    """if command is 'msn'"""
    date, text = quotes_db.msn(db, args)

    response: t.Dict[str, t.Any] = {
        "text": date,
        "attachments": [
            {
                "color": msg_color,
                "blocks": [
                    {
                        "type": "context",
                        "elements": [{"type": "plain_text", "text": msg_user + ":"}],
                    },
                    {"type": "section", "text": {"type": "mrkdwn", "text": msg_text}},
                ],
            }
            for msg_user, msg_text, msg_color in text
        ],
    }
    return response


def cmd_not_found(args: str) -> t.Dict:
    text = (
        f"Beep boop beep! Nôt sure whåt you mean by `{args}`. "
        "Dette er kommandoene jeg skjønner:\n" + command_explanation()
    )
    response: t.Dict[str, t.Any] = {"text": text}
    return response


def cmd_panic(exc: Exception) -> t.Dict:
    text = (
        f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
        " med systemadministrator umiddelbart, før det er for sent. "
        "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    )
    response: t.Dict[str, t.Any] = {"text": text}
    return response


def execute(
    command_str: str,
    args: t.List,
    db_connection: connection,
    drop_pics: droppics.DropPics,
    quotes_db: quotes.Quotes,
) -> t.Dict:
    log.info(f"command: {command_str}")
    log.info(f"args: {args}")

    switch: t.Dict[str, t.Callable] = {
        "ping": cmd_ping,
        "new_channel": cmd_welcome,
        "gargbot": cmd_server_explanation,
        "hvem": partial(cmd_hvem, args, db=db_connection),
        "pic": partial(cmd_pic, args, db=db_connection, drop_pics=drop_pics),
        "forum": partial(cmd_forum, args, db=db_connection, quotes_db=quotes_db),
        "msn": partial(cmd_msn, args, db=db_connection, quotes_db=quotes_db),
    }
    try:
        command_func = switch[command_str]
    except KeyError:
        command_func = partial(cmd_not_found, command_str)

    try:
        return command_func()
    except psycopg2.OperationalError:
        raise
    except (SSLError, dropbox.exceptions.ApiError):
        # Dropbox sometimes gives SSLerrors, (or ApiError if file not there) try again:
        try:
            log.error("SSLerror/ApiError, retrying", exc_info=True)
            return command_func()
        except Exception as exc:
            log.error("Error in command execution", exc_info=True)
            return cmd_panic(exc)
    except Exception as exc:
        log.error("Error in command execution", exc_info=True)
        return cmd_panic(exc)
