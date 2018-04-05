#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from context import congrats, droppics, database_manager
from test_pics import drop_pics, MockDropbox
# from test_quotes import quotes_db


@pytest.fixture
def db_connection():
    db_connection = database_manager.connect_to_database()
    try:
        yield db_connection
    finally:
        db_connection.close()


@pytest.fixture
def drop_pics(db_connection):
    inited_drop_pics = droppics.DropPics(db=db_connection)
    inited_drop_pics.dbx = MockDropbox()
    yield inited_drop_pics


def test_congrat(db_connection, drop_pics):
    birthdays = congrats.get_birthdays()
    response = congrats.get_greeting(birthdays[0], db_connection, drop_pics)
    print(response)
