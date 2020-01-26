#! /usr/bin/env python3.6
# coding: utf-8
import pendulum
import pytest
from psycopg2.extensions import connection

from gargbot_3000 import config, greetings
from tests import conftest


def test_finds_recipient(conn: connection) -> None:
    chosen_user = conftest.users[0]
    test_now = pendulum.instance(chosen_user.birthday, tz=config.tz).add(
        years=conftest.age
    )
    pendulum.set_test_now(test_now)
    recipients = greetings.todays_recipients(conn)
    assert len(recipients) == 1
    recipient = recipients[0]
    assert recipient.nick == chosen_user.slack_nick
    assert recipient.slack_id == chosen_user.slack_id
    assert recipient.age == conftest.age


def test_finds_2_recipients(conn: connection) -> None:
    chosen_user = conftest.users[7]
    test_now = pendulum.instance(chosen_user.birthday, tz=config.tz).add(
        years=conftest.age
    )
    pendulum.set_test_now(test_now)
    recipients = greetings.todays_recipients(conn)
    assert len(recipients) == 2


def test_congrat(conn: connection, dbx: conftest.MockDropbox) -> None:
    chosen_user = conftest.users[0]
    recipient = greetings.Recipient(
        nick=chosen_user.slack_nick, slack_id=chosen_user.slack_id, age=conftest.age
    )
    response = greetings.formulate_congrat(recipient, conn, dbx)
    image_url = response["blocks"][1]["image_url"]
    response_pic = next(pic for pic in conftest.pics if image_url.endswith(pic.path))
    assert chosen_user.slack_id in response["text"]
    assert "Test sentence" in response["text"]
    assert str(conftest.age) in response["text"]
    assert chosen_user.id in response_pic.faces


def test_wait_until_morning(fixed_day):
    night = fixed_day.at(hour=1)
    pendulum.set_test_now(night)
    morning = fixed_day.at(hour=7)
    event = greetings.Event.next()
    assert pendulum.now() + event.until == morning
    assert event.func == greetings.send_congrats


def test_wait_until_midday(fixed_day):
    after_morning = fixed_day.at(hour=7, second=1)
    pendulum.set_test_now(after_morning)
    midday = fixed_day.at(hour=10)
    event = greetings.Event.next()
    assert pendulum.now() + event.until == midday
    assert event.func == greetings.send_report


def test_wait_until_tomorrow_morning(fixed_day):
    after_midday = fixed_day.at(hour=10, second=1)
    pendulum.set_test_now(after_midday)
    tomorrow_morning = fixed_day.add(days=1).at(hour=7)
    event = greetings.Event.next()
    assert pendulum.now() + event.until == tomorrow_morning
    assert event.func == greetings.send_congrats


@pytest.fixture
def fixed_day() -> pendulum.DateTime:
    day_of_test = pendulum.datetime(2020, 1, 2, tz=config.tz)
    return day_of_test
