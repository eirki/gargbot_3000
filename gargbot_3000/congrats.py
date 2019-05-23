#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import random
from operator import attrgetter

import psycopg2

from gargbot_3000 import commands, config

greetings = [
    "Grattis med dagen",
    "Congarats med dagen til deg",
    "Woop woop",
    "Hurra for deg",
    "Huzzah for deg",
    "Supergrattis med dagen",
    "Grættis med dagen",
    "Congratulatore",
    "Gratubalasjoner i massevis",
    "Gratz",
]

jabs = ["din digge jævel!", "kjekken!", "håper det feires!"]

mort_picurl = "https://pbs.twimg.com/media/DAgm_X3WsAAQRGo.jpg"


class Birthday:
    def __init__(self, nick, slack_id, date):
        self.nick = nick
        born_midnight_utc = dt.datetime.combine(date, dt.datetime.min.time())
        born_midnight_local = born_midnight_utc.astimezone(config.tz)
        born_morning_local = born_midnight_local.replace(hour=7)
        self.born = born_morning_local
        self.slack_id = slack_id

    def __repr__(self):
        return f"{self.nick}, {self.age} years. Next bday: {self.next_bday}"

    def seconds_to_bday(self):
        to_next_bday = self.next_bday - dt.datetime.now(config.tz)

        secs = to_next_bday.total_seconds()
        return secs if secs > 0 else 0

    @property
    def age(self):
        return dt.datetime.now(config.tz).year - self.born.year

    @property
    def next_bday(self):
        now = dt.datetime.now(config.tz)
        bday_thisyear = self.born.replace(year=now.year)
        bday_nextyear = self.born.replace(year=now.year + 1)
        next_bday = bday_thisyear if bday_thisyear > now else bday_nextyear
        return next_bday


def get_birthdays(db):
    with db.cursor() as cursor:
        sql_command = "SELECT slack_nick, slack_id, bday FROM user_ids"
        cursor.execute(sql_command)
        data = cursor.fetchall()
    birthdays = [
        Birthday(row["slack_nick"], row["slack_id"], row["bday"]) for row in data
    ]
    birthdays.sort(key=attrgetter("next_bday"))
    return birthdays


def get_greeting(person, db, drop_pics):
    greeting = random.choice(greetings)
    jab = random.choice(jabs)
    text = (
        f"Hurra! Vår felles venn <@{person.slack_id}> fyller {person.age} i dag!\n"
        f"{greeting}, {jab}"
    )
    try:
        person_picurl, date, _ = drop_pics.get_pic(db, [person.nick])
    except psycopg2.OperationalError:
        db.ping(True)
        person_picurl, date, _ = drop_pics.get_pic(db, [person.nick])
    pretty_date = commands.prettify_date(date)
    response = {
        "text": text,
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
            {"type": "image", "image_url": person_picurl, "alt_text": person_picurl},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": pretty_date}]},
            {"type": "image", "image_url": mort_picurl, "alt_text": mort_picurl},
        ],
    }

    return response
