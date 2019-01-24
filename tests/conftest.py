#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
from collections import namedtuple
from pathlib import Path

import pytest
from pytest_postgresql.factories import postgresql
from psycopg2.extras import RealDictCursor

from gargbot_3000 import config
from gargbot_3000 import droppics

# Typing
from psycopg2.extensions import connection


byear = dt.datetime.now(config.tz).year - 28

# fmt: off
User = namedtuple("TestUser", ["db_id", "name", "slack_id", "slack_nick", "bday", "avatar"])
users = [
    User(db_id=2, name="name2", slack_id="s_id2", slack_nick="slack_nick2", bday=dt.datetime(byear, 2, 1), avatar="2.jpg"),
    User(db_id=3, name="name3", slack_id="s_id3", slack_nick="slack_nick3", bday=dt.datetime(byear, 3, 1), avatar="3.jpg"),
    User(db_id=5, name="name5", slack_id="s_id5", slack_nick="slack_nick5", bday=dt.datetime(byear, 5, 1), avatar="5.jpg"),
    User(db_id=6, name="name6", slack_id="s_id6", slack_nick="slack_nick6", bday=dt.datetime(byear, 6, 1), avatar="6.jpg"),
    User(db_id=7, name="name7", slack_id="s_id7", slack_nick="slack_nick7", bday=dt.datetime(byear, 7, 1), avatar="7.jpg"),
    User(db_id=9, name="name9", slack_id="s_id9", slack_nick="slack_nick9", bday=dt.datetime(byear, 9, 1), avatar="9.jpg"),
    User(db_id=10, name="name10", slack_id="s_id10", slack_nick="slack_nick10", bday=dt.datetime(byear, 10, 1), avatar="10.jpg"),
    User(db_id=11, name="name11", slack_id="s_id11", slack_nick="slack_nick11", bday=dt.datetime(byear, 11, 1), avatar="11.jpg"),
]


Pic = namedtuple("TestPic", ["path", "topic", "taken", "faces"])
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

Quote = namedtuple("Quote", ["db_id", "post_text", "post_timestamp", "post_id", "bbcode_uid"])
quotes = [
    Quote(2, "[b]text2[/b]", dt.datetime.fromtimestamp(1172690211), 3, "1dz6ywqv"),
    Quote(3, "[b]text3[/b]", dt.datetime.fromtimestamp(1172690257), 4, "xw0i6wvy"),
    Quote(5, "[b]text4[/b]", dt.datetime.fromtimestamp(1172690319), 5, "3ntrk0df"),
    Quote(6, "[b]text5[/b]", dt.datetime.fromtimestamp(1172690396), 6, "1qmz5uwv"),
    Quote(7, "[b]text6[/b]", dt.datetime.fromtimestamp(1172690466), 7, "2xuife66"),
    Quote(9, "[b]text7[/b]", dt.datetime.fromtimestamp(1172690486), 8, "2wpgc113"),
    Quote(10, "[b]text8[/b]", dt.datetime.fromtimestamp(1172690875), 9, "240k4drr"),
    Quote(11, "[b]text9[/b]", dt.datetime.fromtimestamp(1172691974), 11, "2v1czw2o"),
]

Message = namedtuple("MSN", ["session_id", "msg_time", "msg_color", "from_user", "msg_text", "db_id"])
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
# fmt: on


class MockDropbox:
    responsetuple = namedtuple("response", ["url"])

    def sharing_create_shared_link(self, path):
        return self.responsetuple("https://" + path)


def create_tables(db: connection) -> None:
    with db.cursor() as cursor:
        print(cursor)
        for file in (Path(".") / "schema").iterdir():
            with open(file) as f:
                input = f.read()
            for sql in input.split("\n\n"):
                cursor.execute(sql)


def populate_user_table(db: connection) -> None:
    with db.cursor() as cursor:
        print(cursor)
        for user in users:
            sql_command = """INSERT INTO faces (db_id, name)
            VALUES (%(db_id)s,
                   %(name)s);"""
            data = {"db_id": user.db_id, "name": user.name}
            cursor.execute(sql_command, data)

            sql_command = """INSERT INTO user_ids (db_id, slack_id, slack_nick, first_name, bday, avatar)
            VALUES (%(db_id)s,
                   %(slack_id)s,
                   %(slack_nick)s,
                   %(first_name)s,
                   %(bday)s,
                   %(avatar)s);"""
            data = {
                "db_id": user.db_id,
                "slack_id": user.slack_id,
                "slack_nick": user.slack_nick,
                "first_name": user.name,
                "bday": user.bday,
                "avatar": user.avatar,
            }
            cursor.execute(sql_command, data)


def populate_pics_table(db: connection) -> None:
    with db.cursor() as cursor:
        for pic in pics:
            sql_command = """INSERT INTO dbx_pictures (path, topic, taken)
            VALUES (%(path)s,
                   %(topic)s,
                   %(taken)s);"""
            data = {"path": pic.path, "topic": pic.topic, "taken": pic.taken}
            cursor.execute(sql_command, data)

    with db.cursor() as cursor:
        for pic in pics:
            sql_command = "SELECT pic_id FROM dbx_pictures WHERE path = %(path)s"
            data = {"path": pic.path}
            cursor.execute(sql_command, data)
            pic_id = cursor.fetchone()["pic_id"]
            for db_id in pic.faces:
                sql_command = (
                    "INSERT INTO dbx_pictures_faces (db_id, pic_id)"
                    "VALUES (%(db_id)s, %(pic_id)s);"
                )
                data = {"db_id": db_id, "pic_id": pic_id}
                cursor.execute(sql_command, data)


def populate_quotes_table(db: connection) -> None:
    with db.cursor() as cursor:
        for quote in quotes:
            sql_command = """INSERT INTO phpbb_posts (db_id, post_id, post_timestamp, post_text, bbcode_uid)
            VALUES (%(db_id)s,
                   %(post_id)s,
                   %(post_timestamp)s,
                   %(post_text)s,
                   %(bbcode_uid)s);"""
            data = {
                "db_id": quote.db_id,
                "post_id": quote.post_id,
                "post_timestamp": quote.post_timestamp,
                "post_text": quote.post_text,
                "bbcode_uid": quote.bbcode_uid,
            }
            cursor.execute(sql_command, data)
        for message in messages:
            sql_command = """INSERT INTO msn_messages (session_id, msg_time, msg_color, from_user, msg_text, db_id)
            VALUES (%(session_id)s,
                   %(msg_time)s,
                   %(msg_color)s,
                   %(from_user)s,
                   %(msg_text)s,
                   %(db_id)s);"""
            data = {
                "session_id": message.session_id,
                "msg_time": message.msg_time,
                "msg_color": message.msg_color,
                "from_user": message.from_user,
                "msg_text": message.msg_text,
                "db_id": message.db_id,
            }
            cursor.execute(sql_command, data)


@pytest.fixture
def db_connection(postgresql: connection):
    db = postgresql
    db.cursor_factory = RealDictCursor
    create_tables(db)
    populate_user_table(db)
    populate_pics_table(db)
    populate_quotes_table(db)
    yield db


@pytest.fixture
def drop_pics(db_connection):
    def nothing(*args, **kwargs):
        pass

    droppics.DropPics._connect_dbx = nothing
    inited_drop_pics = droppics.DropPics(db=db_connection)
    inited_drop_pics.dbx = MockDropbox()
    yield inited_drop_pics
