#! /usr/bin/env python3.6
# coding: utf-8
from dataclasses import dataclass
import itertools
from operator import attrgetter
import sys
import time
import typing as t

import aiosql
from dropbox import Dropbox
import pendulum
from psycopg2.extensions import connection
import schedule
from slackclient import SlackClient

from gargbot_3000 import config, database, journey, pictures, task
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
    slack_client = SlackClient(config.slack_bot_user_token)
    for recipient in recipients:
        greet = formulate_congrat(recipient, conn, dbx)
        task.send_response(slack_client, greet, channel=config.main_channel)


def update_journey() -> None:
    conn = database.connect()
    try:
        updates = journey.main(conn)
        if not updates:
            return
        slack_client = SlackClient(config.slack_bot_user_token)
        for update in updates:
            task.send_response(slack_client, update, channel=config.health_channel)
    finally:
        conn.close()


def local_hour_at_utc(hour: int) -> str:
    utc_hour = pendulum.today(config.tz).at(hour).in_timezone("UTC").hour
    formatted = str(utc_hour).zfill(2) + ":00"
    return formatted


def main():
    log.info("GargBot 3000 greeter starter")
    try:
        while True:
            schedule.clear()

            hour = local_hour_at_utc(7)
            log.info(f"Greeter scheduling send_congrats at {hour}")
            schedule.every().day.at(hour).do(send_congrats)

            hour = local_hour_at_utc(12)
            log.info(f"Greeter scheduling update_journey at {hour}")
            schedule.every().day.at(hour).do(update_journey)

            now = pendulum.now(config.tz)
            tomorrow = pendulum.tomorrow(config.tz).at(now.hour, now.minute, now.second)
            seconds_until_this_time_tomorrow = (tomorrow - now).seconds
            for _ in range(seconds_until_this_time_tomorrow):
                schedule.run_pending()
                time.sleep(1)
    except KeyboardInterrupt:
        sys.exit()
