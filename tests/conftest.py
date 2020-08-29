#! /usr/bin/env python3
# coding: utf-8
from collections import namedtuple
from dataclasses import asdict, dataclass
import datetime as dt
from pathlib import Path
import typing as t

from flask import testing
from google.oauth2.credentials import Credentials as GooglefitCredentials
import pendulum
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor, RealDictCursor
import pytest
from withings_api.common import Credentials as WithingsCredentials

from gargbot_3000 import (
    commands,
    config,
    database,
    greetings,
    health,
    journey,
    pictures,
    quotes,
    server,
)
from gargbot_3000.health.googlefit import GooglefitService

age = 28
byear = dt.datetime.now(config.tz).year - age

# flake8: noqa
# fmt: off
@dataclass
class User:
    id: int
    first_name: str
    slack_id: str
    slack_nick: str
    birthday: dt.datetime
    avatar: str
    color_hex: str
    color_name: str

users = [
    User(id=2, first_name="name2", slack_id="s_id2", slack_nick="slack_nick2", birthday=dt.datetime(byear, 2, 1), avatar="2.jpg", color_name="green", color_hex="#3cb44b"),
    User(id=3, first_name="name3", slack_id="s_id3", slack_nick="slack_nick3", birthday=dt.datetime(byear, 3, 1), avatar="3.jpg", color_name="orange", color_hex="#f58231"),
    User(id=5, first_name="name5", slack_id="s_id5", slack_nick="slack_nick5", birthday=dt.datetime(byear, 5, 1), avatar="5.jpg", color_name="purple", color_hex="#911eb4"),
    User(id=6, first_name="name6", slack_id="s_id6", slack_nick="slack_nick6", birthday=dt.datetime(byear, 6, 1), avatar="6.jpg", color_name="cyan", color_hex="#42d4f4"),
    User(id=7, first_name="name7", slack_id="s_id7", slack_nick="slack_nick7", birthday=dt.datetime(byear, 7, 1), avatar="7.jpg", color_name="magenta", color_hex="#f032e6"),
    User(id=9, first_name="name9", slack_id="s_id9", slack_nick="slack_nick9", birthday=dt.datetime(byear, 9, 1), avatar="9.jpg", color_name="lime", color_hex="#bfef45"),
    User(id=10, first_name="name10", slack_id="s_id10", slack_nick="slack_nick10", birthday=dt.datetime(byear, 11, 1), avatar="10.jpg", color_name="red", color_hex="#e6194B"),
    User(id=11, first_name="name11", slack_id="s_id11", slack_nick="slack_nick11", birthday=dt.datetime(byear, 11, 1), avatar="11.jpg", color_name="blue", color_hex="#4363d8"),
]


@dataclass
class Pic:
    path: str
    topic: str
    taken_at: dt.datetime
    faces: t.List[int]

pics = [
    Pic("path/test_pic1", "topic1", dt.datetime(2001, 1, 1), [2]),
    Pic("path/test_pic2", "topic1", dt.datetime(2002, 2, 2), []),
    Pic("path/test_pic3", "topic1", dt.datetime(2003, 3, 3), [11, 2, 3]),
    Pic("path/test_pic4", "topic2", dt.datetime(2004, 4, 4), [2, 3]),
    Pic("path/test_pic5", "topic2", dt.datetime(2005, 5, 5), [7]),
    Pic("path/test_pic6", "topic2", dt.datetime(2006, 6, 6), [5]),
    Pic("path/test_pic7", "topic3", dt.datetime(2007, 7, 7), [3]),
    Pic("path/test_pic8", "topic3", dt.datetime(2008, 8, 8), [2]),
    Pic("path/test_pic9", "topic3", dt.datetime(2009, 9, 9), [2]),
]

@dataclass
class Post:
    id: int
    gargling_id: int
    posted_at: dt.datetime
    content: str
    bbcode_uid: str


forum_posts = [
    Post(2, 2, dt.datetime.fromtimestamp(1172690211), "[b]text2[/b]", "1dz6ywqv"),
    Post(3, 5, dt.datetime.fromtimestamp(1172690257), "[b]text3[/b]", "xw0i6wvy"),
    Post(5, 5, dt.datetime.fromtimestamp(1172690319), "[b]text4[/b]", "3ntrk0df"),
    Post(6, 6, dt.datetime.fromtimestamp(1172690396), "[b]text5[/b]", "1qmz5uwv"),
    Post(7, 7, dt.datetime.fromtimestamp(1172690466), "[b]text6[/b]", "2xuife66"),
    Post(9, 10, dt.datetime.fromtimestamp(1172690486), "[b]text7[/b]", "2wpgc113"),
    Post(10, 9, dt.datetime.fromtimestamp(1172690875), "[b]text8[/b]", "240k4drr"),
    Post(11, 11, dt.datetime.fromtimestamp(1172691974), "[b]text9[/b]", "2v1czw2o"),
]

@dataclass
class Message:
    session_id: str
    sent_at: dt.datetime
    color: str
    from_user: str
    content: str
    gargling_id: int


messages = [
    Message("session1", dt.datetime(2004, 12, 8, 18, 12, 50), "#800080", "msn_nick2", "text1_session1", 2),
    Message("session1", dt.datetime(2004, 12, 8, 18, 13, 12), "#541575", "msn_nick3", "text2_session1", 3),
    Message("session1", dt.datetime(2004, 12, 8, 18, 13, 22), "#800080", "msn_nick2", "text3_session1", 2),
    Message("session2", dt.datetime(2005, 12, 8, 18, 13, 58), "#541575", "msn_nick3", "text1_session2", 3),
    Message("session2", dt.datetime(2005, 12, 8, 18, 14,  6), "#541575", "msn_nick3", "text2_session2", 3),
    Message("session2", dt.datetime(2005, 12, 8, 18, 14, 37), "#800080", "msn_nick2", "text3_session2", 2),
    Message("session3", dt.datetime(2006, 12, 8, 18, 15, 10), "#541575", "msn_nick3", "text1_session3", 3),
    Message("session3", dt.datetime(2006, 12, 8, 18, 19, 24), "#800080", "msn_nick2", "text2_session3", 2),
    Message("session3", dt.datetime(2006, 12, 8, 18, 21,  8), "#541575", "msn_nick3", "text3_session3", 3),
    Message("session3", dt.datetime(2006, 12, 8, 18, 21,  8), "#541575", "msn_nick3", "text4_session3", 3),
]

@dataclass
class Congrat:
    sentence: str


congrats = [
    Congrat("Test sentence1"),
    Congrat("Test sentence2"),
    Congrat("Test sentence3"),
    Congrat("Test sentence4"),
    Congrat("Test sentence5"),
]

# fmt: on


class MockDropbox:
    responsetuple = namedtuple("response", ["url"])

    def sharing_create_shared_link(self, path):
        return self.responsetuple("https://" + path)


def populate_user_table(conn: connection) -> None:
    user_dicts = [asdict(user) for user in users]
    commands.queries.add_users(conn, user_dicts)


def populate_pics_table(conn: connection) -> None:
    for pic in pics:
        pic_id = pictures.queries.add_picture(
            conn, path=pic.path, topic=pic.topic, taken_at=pic.taken_at
        )
        faces = [
            {"picture_id": pic_id, "gargling_id": gargling_id}
            for gargling_id in pic.faces
        ]
        pictures.queries.add_faces(conn, faces)
    pictures.queries.define_args(conn)


def populate_quotes_table(conn: connection) -> None:
    post_dicts = [asdict(post) for post in forum_posts]
    quotes.forum_queries.add_posts(conn, post_dicts)

    message_dicts = [asdict(message) for message in messages]
    quotes.msn_queries.add_messages(conn, message_dicts)


def populate_congrats_table(conn: connection) -> None:
    congrat_dicts = [asdict(congrat) for congrat in congrats]
    greetings.queries.add_congrats(conn, congrat_dicts)


@pytest.fixture()
def conn(postgresql: connection):
    commands.queries.create_schema(postgresql)
    pictures.queries.create_schema(postgresql)
    quotes.forum_queries.create_schema(postgresql)
    quotes.msn_queries.create_schema(postgresql)
    greetings.queries.create_schema(postgresql)
    health.queries.create_schema(postgresql)
    journey.queries.create_schema(postgresql)
    populate_user_table(postgresql)
    populate_pics_table(postgresql)
    populate_quotes_table(postgresql)
    populate_congrats_table(postgresql)
    postgresql.cursor_factory = DictCursor
    postgresql.commit()
    yield postgresql


@pytest.fixture
def dbx(conn):
    mock_dbx = MockDropbox()
    yield mock_dbx


class MockPool(database.ConnectionPool):
    def __init__(self, conn: connection) -> None:
        self.conn = conn

    def _getconn(self) -> connection:
        return self.conn

    def _putconn(self, conn: connection):
        pass

    def closeall(self):
        pass


@pytest.fixture
def client(conn) -> t.Generator[testing.FlaskClient, None, None]:
    server.app.pool = MockPool(conn)
    yield server.app.test_client()
