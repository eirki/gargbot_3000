#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import datetime as dt
from functools import partial
import time
import typing as t

import aiosql
import dropbox
import psycopg2
from psycopg2.extensions import connection
from requests.exceptions import SSLError

from gargbot_3000 import pictures, quotes
from gargbot_3000.journey import achievements
from gargbot_3000.logger import log

queries = aiosql.from_path("sql/gargling.sql", "psycopg2")


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
        "`@gargbot_3000 pic [lark/fe/skating/henging] [kun] [gargling] [år]`: random bilde\n"
        "`@gargbot_3000 forum [garling]`: henter tilfeldig sitat fra ye olde forumet\n"
        "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
        "`@gargbot_3000 rekorder`: current rekorder i vår journey\n"
    )
    return commands if server is False else commands.replace("@gargbot_3000 ", "/")


def cmd_ping() -> dict:
    """if command is 'ping' """
    text = "GargBot 3000 is active. Beep boop beep"
    response: dict[str, t.Any] = {"text": text}
    return response


def cmd_welcome() -> dict:
    """when joining new channel"""
    text = (
        "Hei hei kjære alle sammen!\n"
        "Dette er kommandoene jeg skjønner:\n" + command_explanation()
    )
    response: dict[str, t.Any] = {"text": text}
    return response


def cmd_server_explanation() -> dict:
    expl = command_explanation(server=True)
    text = "Beep boop beep! Dette er kommandoene jeg skjønner:\n" + expl
    response: dict[str, t.Any] = {"text": text}
    return response


def cmd_hvem(args: list[str], conn: connection) -> dict:
    """if command.lower().startswith("hvem")"""
    data = queries.random_first_name(conn)
    user = data["first_name"]
    answ = " ".join(args).replace("?", "!")
    text = f"{user} {answ}"
    response: dict[str, t.Any] = {"text": text}
    return response


def cmd_pic(
    args: t.Optional[list[str]], conn: connection, dbx: dropbox.Dropbox
) -> dict:  # no test coverage
    """if command is 'pic'"""
    picurl, date, description = pictures.get_pic(conn, dbx, args)
    pretty_date = prettify_date(date)
    blocks = []
    image_block = {"type": "image", "image_url": picurl, "alt_text": picurl}
    blocks.append(image_block)
    context_block: dict[str, t.Any] = {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": pretty_date}],
    }
    blocks.append(context_block)
    if description:
        description_block: dict[str, t.Any] = {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": description}],
        }
        blocks.append(description_block)
    response = {"text": picurl, "blocks": blocks}

    return response


def cmd_forum(
    args: t.Optional[list[str]], conn: connection
) -> dict:  # no test coverage
    """if command is 'forum'"""
    text, user, avatar_url, date, url, description = quotes.forum(conn, args)
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


def cmd_msn(args: t.Optional[list[str]], conn: connection) -> dict:  # no test coverage
    """if command is 'msn'"""
    date, text, description = quotes.msn(conn, args)

    response: dict[str, t.Any] = {
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
    if description:
        response["attachments"].append({"type": "mrkdwn", "text": description})
    return response


def cmd_rekorder(conn: connection) -> dict:  # no test coverage
    """if command is 'rekorder'"""
    text = achievements.all_at_date(conn)
    response: dict[str, t.Any] = {"text": text}
    return response


def cmd_not_found(args: str) -> dict:
    text = (
        f"Beep boop beep! Nôt sure whåt you mean by `{args}`. "
        "Dette er kommandoene jeg skjønner:\n" + command_explanation()
    )
    response: dict[str, t.Any] = {"text": text}
    return response


def cmd_panic(exc: Exception) -> dict:
    text = (
        f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
        " med systemadministrator umiddelbart, før det er for sent. "
        "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    )
    response: dict[str, t.Any] = {"text": text}
    return response


def send_response(
    slack_client, response: dict, channel: str, thread_ts: t.Optional[str] = None,
):  # no test coverage
    log.info("Sending to slack: ", response)
    slack_client.chat_postMessage(channel=channel, thread_ts=thread_ts, **response)


def execute(
    command_str: str, args: list, conn: connection, dbx: dropbox.Dropbox
) -> dict:
    log.info(f"command: {command_str}")
    log.info(f"args: {args}")

    switch: dict[str, t.Callable] = {
        "ping": cmd_ping,
        "new_channel": cmd_welcome,
        "gargbot": cmd_server_explanation,
        "hvem": partial(cmd_hvem, args, conn=conn),
        "pic": partial(cmd_pic, args, conn=conn, dbx=dbx),
        "forum": partial(cmd_forum, args, conn=conn),
        "msn": partial(cmd_msn, args, conn=conn),
        "rekorder": partial(cmd_rekorder, conn=conn),
    }
    try:
        command_func = switch[command_str]
    except KeyError:
        command_func = partial(cmd_not_found, command_str)

    try:
        return command_func()
    except psycopg2.OperationalError:  # no test coverage
        raise
    except (SSLError, dropbox.exceptions.ApiError):  # no test coverage
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
