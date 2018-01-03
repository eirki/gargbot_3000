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
def drop_pics():
    db_connection = database_manager.connect_to_database()
    inited_drop_pics = droppics.DropPics(db=db_connection)
    inited_drop_pics.dbx = MockDropbox()
    yield inited_drop_pics
    db_connection.close()


def assert_valid_returns(url, timestamp, description):
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description == '' or description.startswith("Her er et bilde med")


def test_random(drop_pics):
    url, timestamp, description = drop_pics.get_pic(*[])
    assert_valid_returns(url, timestamp, description)


def test_topic(drop_pics):
    topic = list(drop_pics.topics)[0]
    url, timestamp, description = drop_pics.get_pic(*[topic])
    assert_valid_returns(url, timestamp, description)


def test_year(drop_pics):
    year = list(drop_pics.years)[0]
    url, timestamp, description = drop_pics.get_pic(*[year])
    assert_valid_returns(url, timestamp, description)


def test_user(drop_pics):
    user = list(drop_pics.users)[0]
    url, timestamp, description = drop_pics.get_pic(*[user])
    assert_valid_returns(url, timestamp, description)


def test_multiple_args(drop_pics):
    all_args = [
        list(drop_pics.years)
        + list(drop_pics.topics)
        + list(drop_pics.users)
    ]
    permutation = list(itertools.product(*all_args),)[0]
    url, timestamp, description = drop_pics.get_pic(*permutation)
    assert_valid_returns(url, timestamp, description)


# Errors:
def test_error_txt(drop_pics):
    url, timestamp, description = drop_pics.get_pic(*["2000"])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Im so stoopid")
    assert description.endswith("Her er et tilfeldig bilde i stedet:")


def test_error_txt_with_valid(drop_pics):
    user = list(drop_pics.users)[0]
    url, timestamp, description = drop_pics.get_pic(*["2000", user])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Im so stoopid")
    assert "Her er et bilde med" in description


def test_error_txt_with_impossible_combination(drop_pics):
    url, timestamp, description = drop_pics.get_pic(*["2002", "fe"])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert description.startswith("Fant ikke")
    assert "Her er et bilde med" in description
