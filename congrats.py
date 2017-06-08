#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import datetime as dt
from operator import attrgetter
import json
from os import path
import random

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
    now = dt.datetime.now()

    def __init__(self, nick, date):
        self.nick = nick
        self.bday = dt.datetime.strptime(f"{date}.08.00", "%d.%m.%Y.%H.%M")
        self.next_bday = self.get_next_bday(self.bday)
        self.seconds_to_bday = (self.next_bday - self.now).total_seconds()
        self.age = self.now.year - self.bday.year
        self.slack_id = config.slack_nick_to_id[nick]

    def __repr__(self):
        return f"{self.nick}: {self.next_bday}, {self.age} years"

    @classmethod
    def get_next_bday(self, bday):
        bday_thisyear = dt.datetime(hour=bday.hour, minute=bday.minute, day=bday.day, month=bday.month, year=self.now.year)
        next_bday = (bday_thisyear if bday_thisyear > self.now
                     else dt.datetime(hour=bday.hour, minute=bday.minute, day=bday.day, month=bday.month, year=self.now.year + 1))
        return next_bday


def get_birthdays():
    with open(path.join(config.home, "data", "birthdays.json")) as j:
        data = json.load(j)
    birthdays = [Birthday(nick, date) for nick, date in data]
    birthdays.sort(key=attrgetter("next_bday"))
    return birthdays


def get_greeting(person):
    greeting = random.choice(greetings)
    jab = random.choice(jabs)
    text = f"Hurra! Vår felles venn <@{person.slack_id}> fyller {person.age} i dag!\n {greeting}, {jab}"
    return text
