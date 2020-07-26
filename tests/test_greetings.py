#! /usr/bin/env python3.6
# coding: utf-8
import pendulum
from psycopg2.extensions import connection
import pytest

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
