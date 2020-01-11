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
    recipients = greetings.Recipient.get_todays(conn)
    assert len(recipients) == 1
    recipient = recipients[0]
    assert recipient.nick == chosen_user.slack_nick
    assert recipient.slack_id == chosen_user.slack_id
    assert recipient.age == conftest.age


def test_finds_2_recipients(conn: connection) -> None:
    chosen_user = conftest.users[7]
    test_now = pendulum.instance(chosen_user.bday, tz=config.tz).add(years=conftest.age)
    pendulum.set_test_now(test_now)
    recipients = greetings.Recipient.get_todays(conn)
    assert len(recipients) == 2


def test_congrat(conn: connection, drop_pics: DropPics) -> None:
    chosen_user = conftest.users[0]
    recipient = greetings.Recipient(
        nick=chosen_user.slack_nick, slack_id=chosen_user.slack_id, age=conftest.age
    )
    response = recipient.get_greeting(conn, drop_pics)
    image_url = response["blocks"][1]["image_url"]
    response_pic = next(pic for pic in conftest.pics if image_url.endswith(pic.path))
    assert chosen_user.slack_id in response["text"]
    assert "Test sentence" in response["text"]
    assert str(conftest.age) in response["text"]
    assert chosen_user.db_id in response_pic.faces


def test_wait_same_day():
    night_today_tz = pendulum.today(config.tz).add(hours=1)
    morning_today_tz = pendulum.today(config.tz).add(hours=7)
    pendulum.set_test_now(night_today_tz)
    until_next = greetings.get_period_to_morning()
    assert night_today_tz + until_next == morning_today_tz


def test_wait_next_day():
    midday_today_tz = pendulum.today(config.tz).add(hours=12)
    morning_tmrw_tz = pendulum.tomorrow(config.tz).add(hours=7)
    pendulum.set_test_now(midday_today_tz)
    until_next = greetings.get_period_to_morning()
    assert midday_today_tz + until_next == morning_tmrw_tz


def test_wait_next_day2():
    late_morning_today_tz = pendulum.today(config.tz).add(hours=7, seconds=1)
    morning_tmrw_tz = pendulum.tomorrow(config.tz).add(hours=7)
    pendulum.set_test_now(late_morning_today_tz)
    until_next = greetings.get_period_to_morning()
    assert late_morning_today_tz + until_next == morning_tmrw_tz
