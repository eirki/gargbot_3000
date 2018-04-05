#! /usr/bin/env python3.6
# coding: utf-8
import itertools
from collections import namedtuple

import pytest

from context import droppics, database_manager


class MockDropbox:
    responsetuple = namedtuple("response", ["url"])

    def sharing_create_shared_link(self, path):
        return self.responsetuple("https://www.dropbox.com/s/sample/sample.JPG?dl=0")


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


def assert_valid_returns(url, timestamp, description):
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description == '' or description.startswith("Her er et bilde med")


def test_random(db_connection, drop_pics):
    url, timestamp, description = drop_pics.get_pic(db_connection, *[])
    assert_valid_returns(url, timestamp, description)


def test_topic(db_connection, drop_pics):
    topic = list(drop_pics.topics)[0]
    url, timestamp, description = drop_pics.get_pic(db_connection, *[topic])
    assert_valid_returns(url, timestamp, description)


def test_year(db_connection, drop_pics):
    year = list(drop_pics.years)[0]
    url, timestamp, description = drop_pics.get_pic(db_connection, *[year])
    assert_valid_returns(url, timestamp, description)


def test_user(db_connection, drop_pics):
    user = list(drop_pics.users)[0]
    url, timestamp, description = drop_pics.get_pic(db_connection, *[user])
    assert_valid_returns(url, timestamp, description)


def test_multiple_args(db_connection, drop_pics):
    all_args = [
        list(drop_pics.years)
        + list(drop_pics.topics)
        + list(drop_pics.users)
    ]
    permutation = list(itertools.product(*all_args),)[0]
    url, timestamp, description = drop_pics.get_pic(db_connection, *permutation)
    assert_valid_returns(url, timestamp, description)


# Errors:
def test_error_txt(db_connection, drop_pics):
    url, timestamp, description = drop_pics.get_pic(db_connection, *["2000"])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Im so stoopid")
    assert description.endswith("Her er et tilfeldig bilde i stedet:")


def test_error_txt_with_valid(db_connection, drop_pics):
    user = list(drop_pics.users)[0]
    url, timestamp, description = drop_pics.get_pic(db_connection, *["2000", user])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Im so stoopid")
    assert "Her er et bilde med" in description


def test_error_txt_with_impossible_combination(db_connection, drop_pics):
    url, timestamp, description = drop_pics.get_pic(db_connection, *["2002", "fe"])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Fant ikke")
    assert "Her er et bilde med" in description
