#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import datetime as dt
from operator import attrgetter
import json
from os import path
import random

import MySQLdb

import config


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

jabs = [
    "din digge jævel!",
    "kjekken!",
    "håper det feires!"
]


class Birthday:
    def __init__(self, nick, date):
        self.nick = nick
        born_midnight_utc = dt.datetime.strptime(f"{date}.00.00.+0000", "%d.%m.%Y.%H.%M.%z")
        born_midnight_local = born_midnight_utc.astimezone(config.tz)
        born_morning_local = born_midnight_local.replace(hour=7)
        self.born = born_morning_local
        self.slack_id = config.slack_nick_to_id[nick]

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
        bday_nextyear = self.born.replace(year=now.year+1)
        next_bday = bday_thisyear if bday_thisyear > now else bday_nextyear
        return next_bday


def get_birthdays():
    with open(path.join(config.home, "data", "birthdays.json")) as j:
        data = json.load(j)
    birthdays = [Birthday(nick, date) for nick, date in data]
    birthdays.sort(key=attrgetter("next_bday"))
    return birthdays


def get_greeting(person, drop_pics):
    greeting = random.choice(greetings)
    jab = random.choice(jabs)
    text = (
        f"Hurra! Vår felles venn <@{person.slack_id}> fyller {person.age} i dag!\n"
        f" {greeting}, {jab}"
    )
    congrats_picurl = "https://pbs.twimg.com/media/DAgm_X3WsAAQRGo.jpg"

    try:
        person_picurl, timestamp, error_text = drop_pics.get_pic(person.nick)
    except MySQLdb.OperationalError:
        drop_pics.db.ping(True)
        person_picurl, timestamp, error_text = drop_pics.get_pic(person.nick)

    response = {
        "text": text,
        "attachments": [
            {"fallback": person_picurl, "image_url": person_picurl, "ts": timestamp},
            {"fallback": congrats_picurl, "image_url": congrats_picurl}
        ]
    }

    return response


if __name__ == '__main__':
    log.info(get_birthdays())
