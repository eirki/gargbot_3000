#! /usr/bin/env python3.6
# coding: utf-8
from psycopg2.extensions import connection

from gargbot_3000 import congrats
from gargbot_3000.droppics import DropPics
from tests import conftest


def test_congrat(db_connection: connection, drop_pics: DropPics) -> None:
    chosen_user = conftest.users[0]
    birthdays = congrats.get_birthdays(db=db_connection)
    person = next(
        person for person in birthdays if person.nick == chosen_user.slack_nick
    )

    response = congrats.get_greeting(person, db_connection, drop_pics)
    image_url = response["blocks"][1]["image_url"]
    response_pic = next(pic for pic in conftest.pics if image_url.endswith(pic.path))
    assert chosen_user.slack_id in response["text"]
    assert "28" in response["text"]
    assert chosen_user.db_id in response_pic.faces
