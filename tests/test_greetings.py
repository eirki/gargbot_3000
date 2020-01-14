#! /usr/bin/env python3.6
# coding: utf-8
import pendulum
from psycopg2.extensions import connection

from gargbot_3000 import config, greetings
from gargbot_3000.pictures import DropPics
from tests import conftest


def test_finds_recipient(conn: connection) -> None:
    chosen_user = conftest.users[0]
    test_now = pendulum.instance(chosen_user.bday, tz=config.tz).add(years=conftest.age)
    pendulum.set_test_now(test_now)
    recipients = greetings.todays_recipients(conn)
    assert len(recipients) == 1
    recipient = recipients[0]
    assert recipient.nick == chosen_user.slack_nick
    assert recipient.slack_id == chosen_user.slack_id
    assert recipient.age == conftest.age


def test_finds_2_recipients(conn: connection) -> None:
    chosen_user = conftest.users[7]
    test_now = pendulum.instance(chosen_user.bday, tz=config.tz).add(years=conftest.age)
    pendulum.set_test_now(test_now)
    recipients = greetings.todays_recipients(conn)
    assert len(recipients) == 2


def test_congrat(conn: connection, drop_pics: DropPics) -> None:
    chosen_user = conftest.users[0]
    recipient = greetings.Recipient(
        nick=chosen_user.slack_nick, slack_id=chosen_user.slack_id, age=conftest.age
    )
    response = greetings.formulate_congrats(recipient, conn, drop_pics)
    image_url = response["blocks"][1]["image_url"]
    response_pic = next(pic for pic in conftest.pics if image_url.endswith(pic.path))
    assert chosen_user.slack_id in response["text"]
    assert "Test sentence" in response["text"]
    assert str(conftest.age) in response["text"]
    assert chosen_user.db_id in response_pic.faces


def test_wait_same_day():
    night = pendulum.datetime(2020, 1, 2, hour=1, tz=config.tz)
    morning = pendulum.datetime(2020, 1, 2, hour=7, tz=config.tz)
    pendulum.set_test_now(night)
    until_next = greetings.get_period_to_morning()
    assert pendulum.now() + until_next == morning


def test_wait_next_day():
    noon = pendulum.datetime(2020, 1, 2, hour=12, tz=config.tz)
    tomorrow_morning = pendulum.datetime(2020, 1, 3, hour=7, tz=config.tz)
    pendulum.set_test_now(noon)
    until_next = greetings.get_period_to_morning()
    assert pendulum.now() + until_next == tomorrow_morning


def test_wait_next_day2():
    late_morning = pendulum.datetime(2020, 1, 2, hour=7, second=1, tz=config.tz)
    tomorrow_morning = pendulum.datetime(2020, 1, 3, hour=7, tz=config.tz)
    pendulum.set_test_now(late_morning)
    until_next = greetings.get_period_to_morning()
    assert pendulum.now() + until_next == tomorrow_morning
