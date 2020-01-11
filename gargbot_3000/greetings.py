#! /usr/bin/env python3.6
# coding: utf-8
import sys
import time
import typing as t

import aiosql
import pendulum
import psycopg2
from psycopg2.extensions import connection
from slackclient import SlackClient

from dataclasses import dataclass
from gargbot_3000 import config, database_manager, health, pictures, task
from gargbot_3000.logger import log

queries = aiosql.from_path("schema/congrats.sql", "psycopg2")

mort_picurl = "https://pbs.twimg.com/media/DAgm_X3WsAAQRGo.jpg"


@dataclass
class Recipient:
    nick: str
    slack_id: str
    age: int

    @classmethod
    def get_todays(cls, conn: connection) -> t.List["Recipient"]:
        now_tz = pendulum.now(config.tz)
        with conn.cursor() as cursor:
            sql_command = (
                "SELECT slack_nick, slack_id, EXTRACT(YEAR FROM bday)::int as year "
                "FROM user_ids "
                "WHERE EXTRACT(MONTH FROM bday) = %(month)s "
                "AND EXTRACT(DAY FROM bday) = %(day)s"
            )
            cursor.execute(sql_command, {"month": now_tz.month, "day": now_tz.day})
            data = cursor.fetchall()
        recipients = [
            cls(
                nick=row["slack_nick"],
                slack_id=row["slack_id"],
                age=(now_tz.year - row["year"]),
            )
            for row in data
        ]
        return recipients

    def get_greeting(self, conn: connection, drop_pics) -> t.Dict:
        sentence = self.get_sentence(conn)
        text = (
            f"Hurra! Vår felles venn <@{self.slack_id}> fyller {self.age} i dag!\n"
            f"{sentence}"
        )
        try:
            person_picurl, date, _ = drop_pics.get_pic(conn, [self.nick])
        except psycopg2.OperationalError:
            conn.ping(True)
            person_picurl, date, _ = drop_pics.get_pic(conn, [self.nick])
        response = {
            "text": text,
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": text}},
                {
                    "type": "image",
                    "image_url": person_picurl,
                    "alt_text": person_picurl,
                },
                {"type": "image", "image_url": mort_picurl, "alt_text": mort_picurl},
            ],
        }

        return response

    @staticmethod
    def get_sentence(conn: connection) -> str:
        with conn.cursor() as cursor:
            sql_command = "SELECT sentence FROM congrats ORDER BY RANDOM() LIMIT 1"
            cursor.execute(sql_command)
            result = cursor.fetchone()
        sentence = result["sentence"]
        return sentence

    def get_greet(self, conn: connection) -> dict:
        drop_pics = pictures.DropPics()
        response = self.get_greeting(conn, drop_pics)
        return response


def get_period_to_morning() -> pendulum.Period:
    morning_today = pendulum.today(config.tz).add(hours=7)
    morning_tmrw = pendulum.tomorrow(config.tz).add(hours=7)
    now = pendulum.now(config.tz)
    next_greeting_time = morning_today if morning_today > now else morning_tmrw
    until_next = next_greeting_time - now
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
            time.sleep(until_next.total_seconds())
            try:
                slack_client = SlackClient(config.slack_bot_user_token)
                conn = database_manager.connect_to_database()
                recipients = Recipient.get_todays(conn)
                log.info(f"Recipients today {recipients}")
                for recipient in recipients:
                    greet = recipient.get_greet(conn)
                    task.send_response(slack_client, greet, channel=config.main_channel)
                report = health.get_daily_report(conn)
                if report is not None:
                    task.send_response(
                        slack_client, report, channel=config.health_channel
                    )
                conn.close()
            except Exception:
                log.error("Error in command execution", exc_info=True)
    except KeyboardInterrupt:
        sys.exit()
