#! /usr/bin/env python3.6
# coding: utf-8
import itertools
import sys
import time
import typing as t
from operator import attrgetter

import aiosql
import pendulum
from psycopg2.extensions import connection
from slackclient import SlackClient

from dataclasses import dataclass
from gargbot_3000 import config, database, health, pictures, task
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


def formulate_congrat(recipient: Recipient, conn: connection, drop_pics) -> t.Dict:
    sentence = queries.random_sentence(conn)["sentence"]
    text = (
        f"Hurra! Vår felles venn <@{recipient.slack_id}> fyller {recipient.age} i dag!\n"
        f"{sentence}"
    )
    person_picurl, date, _ = drop_pics.get_pic(conn, [recipient.nick])
    response = {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "image", "image_url": person_picurl, "alt_text": person_picurl},
            {"type": "image", "image_url": mort_picurl, "alt_text": mort_picurl},
        ],
    }

    return response


def send_congrats(conn: connection, slack_client: SlackClient):
    drop_pics = pictures.DropPics()
    recipients = todays_recipients(conn)
    log.info(f"Recipients today {recipients}")
    for recipient in recipients:
        greet = formulate_congrat(recipient, conn, drop_pics)
        task.send_response(slack_client, greet, channel=config.main_channel)


def send_report(conn: connection, slack_client: SlackClient):
    report = health.report(conn)
    if report is not None:
        task.send_response(slack_client, report, channel=config.health_channel)


@dataclass(frozen=True)
class Event:
    until: pendulum.Period
    func: t.Callable

    @staticmethod
    def possible():
        types = [(10, send_report), (7, send_congrats)]
        times = (pendulum.today, pendulum.tomorrow)
        return itertools.product(times, types)

    @staticmethod
    def next() -> "Event":
        events = []
        now = pendulum.now()
        for day, (hour, func) in Event.possible():
            when = day(config.tz).at(hour)
            if when.is_past():
                continue
            events.append(Event(until=(when - now), func=func))
        events.sort(key=attrgetter("until"))
        event = events[0]
        return event


def main() -> None:
    log.info("GargBot 3000 greeter starter")
    try:
        while True:
            event = Event.next()
            log.info(
                f"Next greeting check at: {event.until.end}, "
                f"sleeping for {event.until.in_words()}"
            )
            time.sleep(event.until.total_seconds())
            try:
                slack_client = SlackClient(config.slack_bot_user_token)
                conn = database.connect()
                event.func(conn, slack_client)
            except Exception:
                log.error("Error in command execution", exc_info=True)
            finally:
                conn.close()
    except KeyboardInterrupt:
        sys.exit()
