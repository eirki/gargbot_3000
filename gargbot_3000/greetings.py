#! /usr/bin/env python3
# coding: utf-8
from dataclasses import dataclass
import typing as t

import aiosql
from dropbox import Dropbox
import pendulum
from psycopg2.extensions import connection
import slack

from gargbot_3000 import commands, config, database, pictures
from gargbot_3000.logger import log

queries = aiosql.from_path("sql/congrats.sql", "psycopg2")

mort_picurl = "https://pbs.twimg.com/media/DAgm_X3WsAAQRGo.jpg"


@dataclass(frozen=True)
class Recipient:
    nick: str
    slack_id: str
    age: int


def todays_recipients(conn: connection) -> t.List[Recipient]:
    now_tz = pendulum.now(config.tz)
    data = queries.congrats_for_date(conn, month=now_tz.month, day=now_tz.day)
    recipients = [
        Recipient(
            nick=row["slack_nick"],
            slack_id=row["slack_id"],
            age=(now_tz.year - row["year"]),
        )
        for row in data
    ]
    return recipients


def formulate_congrat(recipient: Recipient, conn: connection, dbx: Dropbox) -> t.Dict:
    sentence = queries.random_sentence(conn)["sentence"]
    text = (
        f"Hurra! Vår felles venn <@{recipient.slack_id}> fyller {recipient.age} i dag!\n"
        f"{sentence}"
    )
    person_picurl, date, _ = pictures.get_pic(conn, dbx, [recipient.nick])
    response = {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "image", "image_url": person_picurl, "alt_text": person_picurl},
            {"type": "image", "image_url": mort_picurl, "alt_text": mort_picurl},
        ],
    }

    return response


def send_congrats() -> None:
    dbx = pictures.connect_dbx()
    conn = database.connect()
    recipients = todays_recipients(conn)
    if not recipients:
        return
    log.info(f"Recipients today {recipients}")
    slack_client = slack.WebClient(config.slack_bot_user_token)
    for recipient in recipients:
        greet = formulate_congrat(recipient, conn, dbx)
        commands.send_response(slack_client, greet, channel=config.main_channel)
