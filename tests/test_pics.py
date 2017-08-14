#! /usr/bin/env python3.6
# coding: utf-8
import itertools
from collections import namedtuple

import pytest

from context import config, droppics, database_manager


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


def assert_valid_returns(url, timestamp, error_text):
    assert url.startswith("https")
    assert type(timestamp) == int
    assert error_text == ''


def test_random(drop_pics):
    url, timestamp, error_text = drop_pics.get_pic(*[])
    assert_valid_returns(url, timestamp, error_text)


def test_topic(drop_pics):
    topic = list(drop_pics.topics)[0]
    url, timestamp, error_text = drop_pics.get_pic(*[topic])
    assert_valid_returns(url, timestamp, error_text)


def test_year(drop_pics):
    year = list(drop_pics.years)[0]
    url, timestamp, error_text = drop_pics.get_pic(*[year])
    assert_valid_returns(url, timestamp, error_text)


def test_user(drop_pics):
    user = list(config.slack_nicks_to_garg_ids.keys())[0]
    url, timestamp, error_text = drop_pics.get_pic(*[user])
    assert_valid_returns(url, timestamp, error_text)


def test_multiple_args(drop_pics):
    all_args = [
        list(drop_pics.years)
        + list(config.slack_nicks_to_garg_ids.keys())
        + list(config.slack_nicks_to_garg_ids.keys())
    ]
    permutation = list(itertools.product(*all_args),)[0]
    url, timestamp, error_text = drop_pics.get_pic(*permutation)
    assert_valid_returns(url, timestamp, error_text)


# Errors:
def test_error_txt(drop_pics):
    url, timestamp, error_text = drop_pics.get_pic(*["2000"])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert error_text.startswith("Im so stoopid")
    assert error_text.endswith("Her er et tilfeldig bilde i stedet:")


def test_error_txt_with_valid(drop_pics):
    user = list(config.slack_nicks_to_garg_ids.keys())[0]
    url, timestamp, error_text = drop_pics.get_pic(*["2000", user])
    assert url.startswith("https")
    assert type(timestamp) == int
    assert error_text.startswith("Im so stoopid")
    assert "Her er et bilde med" in error_text
