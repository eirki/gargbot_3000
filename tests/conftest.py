#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import typing as t
from collections import namedtuple
from pathlib import Path

import pytest
from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor

from dataclasses import asdict, dataclass
from gargbot_3000 import commands, config, droppics, greetings, health, quotes

age = 28
byear = dt.datetime.now(config.tz).year - age

# flake8: noqa
# fmt: off
@dataclass
class User:
    db_id: int
    first_name: str
    slack_id: str
    slack_nick: str
    bday: dt.datetime
    avatar: str

users = [
    User(db_id=2, first_name="name2", slack_id="s_id2", slack_nick="slack_nick2", bday=dt.datetime(byear, 2, 1), avatar="2.jpg"),
    User(db_id=3, first_name="name3", slack_id="s_id3", slack_nick="slack_nick3", bday=dt.datetime(byear, 3, 1), avatar="3.jpg"),
    User(db_id=5, first_name="name5", slack_id="s_id5", slack_nick="slack_nick5", bday=dt.datetime(byear, 5, 1), avatar="5.jpg"),
    User(db_id=6, first_name="name6", slack_id="s_id6", slack_nick="slack_nick6", bday=dt.datetime(byear, 6, 1), avatar="6.jpg"),
    User(db_id=7, first_name="name7", slack_id="s_id7", slack_nick="slack_nick7", bday=dt.datetime(byear, 7, 1), avatar="7.jpg"),
    User(db_id=9, first_name="name9", slack_id="s_id9", slack_nick="slack_nick9", bday=dt.datetime(byear, 9, 1), avatar="9.jpg"),
    User(db_id=10, first_name="name10", slack_id="s_id10", slack_nick="slack_nick10", bday=dt.datetime(byear, 11, 1), avatar="10.jpg"),
    User(db_id=11, first_name="name11", slack_id="s_id11", slack_nick="slack_nick11", bday=dt.datetime(byear, 11, 1), avatar="11.jpg"),
]


@dataclass
class Pic:
    path: str
    topic: str
    taken: dt.datetime
    faces: t.List[int]

pics = [
    Pic("path/test_pic1", "topic1", dt.datetime(2001, 1, 1), [2]),
    Pic("path/test_pic2", "topic1", dt.datetime(2002, 2, 2), []),
    Pic("path/test_pic3", "topic1", dt.datetime(2003, 3, 3), [11, 2, 3]),
    Pic("path/test_pic4", "topic2", dt.datetime(2004, 4, 4), [2, 3]),
    Pic("path/test_pic5", "topic2", dt.datetime(2005, 5, 5), [7]),
    Pic("path/test_pic6", "topic2", dt.datetime(2006, 6, 6), [5]),
    Pic("path/test_pic7", "topic3", dt.datetime(2007, 7, 7), [2]),
    Pic("path/test_pic8", "topic3", dt.datetime(2008, 8, 8), [2]),
    Pic("path/test_pic9", "topic3", dt.datetime(2009, 9, 9), [2]),
]

@dataclass
class ForumPost:
    db_id: int
    post_text: str
    post_timestamp: dt.datetime
    post_id: int
    bbcode_uid: str


forum_posts = [
    ForumPost(2, "[b]text2[/b]", dt.datetime.fromtimestamp(1172690211), 3, "1dz6ywqv"),
    ForumPost(3, "[b]text3[/b]", dt.datetime.fromtimestamp(1172690257), 4, "xw0i6wvy"),
    ForumPost(5, "[b]text4[/b]", dt.datetime.fromtimestamp(1172690319), 5, "3ntrk0df"),
    ForumPost(6, "[b]text5[/b]", dt.datetime.fromtimestamp(1172690396), 6, "1qmz5uwv"),
    ForumPost(7, "[b]text6[/b]", dt.datetime.fromtimestamp(1172690466), 7, "2xuife66"),
    ForumPost(9, "[b]text7[/b]", dt.datetime.fromtimestamp(1172690486), 8, "2wpgc113"),
    ForumPost(10, "[b]text8[/b]", dt.datetime.fromtimestamp(1172690875), 9, "240k4drr"),
    ForumPost(11, "[b]text9[/b]", dt.datetime.fromtimestamp(1172691974), 11, "2v1czw2o"),
]

@dataclass
class Message:
    session_id: str
    msg_time: dt.datetime
    msg_color: str
    from_user: str
    msg_text: str
    db_id: int


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

@dataclass
class FitbitUser:
    fitbit_id: str
    db_id: t.Optional[int]
    access_token: str
    refresh_token: str
    expires_at: float


fitbit_users = [
    FitbitUser("fitbit_id1", 2, "access_token1", "refresh_token1", 1573921366.6757),
    FitbitUser("fitbit_id2", 3, "access_token2", "refresh_token2", 1573921366.6757),
    FitbitUser("fitbit_id3", None, "access_token3", "refresh_token3", 1573921366.6757),
    FitbitUser("fitbit_id5", 5, "access_token5", "refresh_token5", 1573921366.6757),
]

@dataclass
class HealthReport:
    fitbit_id: str


health_report_users = [
    HealthReport("fitbit_id1"),
    HealthReport("fitbit_id5")
]
# fmt: on


class MockDropbox:
    responsetuple = namedtuple("response", ["url"])

    def sharing_create_shared_link(self, path):
        return self.responsetuple("https://" + path)


def populate_user_table(conn: connection) -> None:
    commands.queries.create_schema(conn)
    user_dicts = [asdict(user) for user in users]
    commands.queries.add_users(conn, user_dicts)


def populate_pics_table(conn: connection) -> None:
    droppics.queries.create_schema(conn)
    for pic in pics:
        pic_id = droppics.queries.add_picture(
            conn, path=pic.path, topic=pic.topic, taken=pic.taken
        )
        faces = [{"pic_id": pic_id, "db_id": db_id} for db_id in pic.faces]
        droppics.queries.add_faces(conn, faces)
    droppics.queries.define_args(conn)


def populate_quotes_table(conn: connection) -> None:
    quotes.forum_queries.create_schema(conn)
    post_dicts = [asdict(post) for post in forum_posts]
    quotes.forum_queries.add_posts(conn, post_dicts)

    quotes.msn_queries.create_schema(conn)
    message_dicts = [asdict(message) for message in messages]
    quotes.msn_queries.add_messages(conn, message_dicts)


def populate_congrats_table(conn: connection) -> None:
    greetings.queries.create_schema(conn)
    congrat_dicts = [asdict(congrat) for congrat in congrats]
    greetings.queries.add_congrats(conn, congrat_dicts)


def populate_health_table(conn: connection) -> None:
    health.queries.create_schema(conn)
    for fitbit_user in fitbit_users:
        health.queries.persist_token(
            conn,
            user_id=fitbit_user.fitbit_id,
            access_token=fitbit_user.access_token,
            refresh_token=fitbit_user.refresh_token,
            expires_at=fitbit_user.expires_at,
        )
        if fitbit_user.db_id is None:
            continue
        health.queries.match_ids(
            conn, fitbit_id=fitbit_user.fitbit_id, db_id=fitbit_user.db_id
        )
    for health_report_user in health_report_users:
        sql_command = "INSERT INTO health_report (fitbit_id) VALUES (%(fitbit_id)s);"
        conn.cursor().execute(sql_command, asdict(health_report_user))


@pytest.fixture()
def db_connection(postgresql: connection):
    populate_pics_table(postgresql)
    populate_user_table(postgresql)
    populate_quotes_table(postgresql)
    populate_congrats_table(postgresql)
    populate_health_table(postgresql)
    postgresql.cursor_factory = RealDictCursor
    yield postgresql


@pytest.fixture
def drop_pics(db_connection):
    def nothing(*args, **kwargs):
        pass

    droppics.DropPics._connect_dbx = nothing
    inited_drop_pics = droppics.DropPics()
    inited_drop_pics.dbx = MockDropbox()
    yield inited_drop_pics
