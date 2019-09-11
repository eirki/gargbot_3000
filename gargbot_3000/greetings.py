#! /usr/bin/env python3.6
# coding: utf-8
import sys
import time
import typing as t

import pendulum
import psycopg2
from psycopg2.extensions import connection
from slackclient import SlackClient

from dataclasses import dataclass
from gargbot_3000 import config, database_manager, droppics, task
from gargbot_3000.logger import log

mort_picurl = "https://pbs.twimg.com/media/DAgm_X3WsAAQRGo.jpg"


@dataclass
class Recipient:
    nick: str
    slack_id: str
    age: int


def get_recipients(db: connection) -> t.List[Recipient]:
    now_tz = pendulum.now(config.tz)
    with db.cursor() as cursor:
        sql_command = (
            "SELECT slack_nick, slack_id, EXTRACT(YEAR FROM bday)::int as year "
            "FROM user_ids "
            "WHERE EXTRACT(MONTH FROM bday) = %(month)s "
            "AND EXTRACT(DAY FROM bday) = %(day)s"
        )
        cursor.execute(sql_command, {"month": now_tz.month, "day": now_tz.day})
        data = cursor.fetchall()
    recipients = [
        Recipient(
            nick=row["slack_nick"],
            slack_id=row["slack_id"],
            age=(now_tz.year - row["year"]),
        )
        for row in data
    ]
    return recipients


def get_sentence(db: connection) -> str:
    with db.cursor() as cursor:
        sql_command = "SELECT sentence FROM congrats ORDER BY RANDOM() LIMIT 1"
        cursor.execute(sql_command)
        result = cursor.fetchone()
    sentence = result["sentence"]
    return sentence


def get_greeting(person: Recipient, db: connection, drop_pics) -> t.Dict:
    sentence = get_sentence(db)
    text = (
        f"Hurra! Vår felles venn <@{person.slack_id}> fyller {person.age} i dag!\n"
        f"{sentence}"
    )
    try:
        person_picurl, date, _ = drop_pics.get_pic(db, [person.nick])
    except psycopg2.OperationalError:
        db.ping(True)
        person_picurl, date, _ = drop_pics.get_pic(db, [person.nick])
    response = {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "image", "image_url": person_picurl, "alt_text": person_picurl},
            {"type": "image", "image_url": mort_picurl, "alt_text": mort_picurl},
        ],
    }

    return response


def handle_greet() -> None:
    db_connection = database_manager.connect_to_database()
    recipients = get_recipients(db_connection)
    log.info(f"Recipients today {recipients}")
    for recipient in recipients:
        drop_pics = droppics.DropPics(db=db_connection)
        slack_client = SlackClient(config.slack_bot_user_token)
        response = get_greeting(recipient, db_connection, drop_pics)
        task.send_response(slack_client, response=response, channel=config.main_channel)
    db_connection.close()


def get_period_to_morning() -> pendulum.Period:
    morning_today_tz = pendulum.today(config.tz).add(hours=7)
    morning_tmrw_tz = pendulum.tomorrow(config.tz).add(hours=7)
    now_tz = pendulum.now(config.tz)
    next_greeting_time = (
        morning_today_tz if morning_today_tz > now_tz else morning_tmrw_tz
    )
    until_next = next_greeting_time - now_tz
    return until_next


def main() -> None:
    log.info("GargBot 3000 greeter starter")
    try:
        while True:
            until_next = get_period_to_morning()
            log.info(
                f"Next greeting check at: {until_next.end}, "
                f"sleeping for {until_next.in_words()}"
            )
            time.sleep(until_next.seconds)
            try:
                handle_greet()
            except Exception:
                log.error("Error in command execution", exc_info=True)
    except KeyboardInterrupt:
        sys.exit()
