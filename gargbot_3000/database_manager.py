#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import os
import re
import typing as t
from contextlib import contextmanager
from pathlib import Path
from xml.dom.minidom import parseString

import dropbox
import psycopg2
from PIL import Image
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor
from psycopg2.pool import ThreadedConnectionPool

from gargbot_3000 import config
from gargbot_3000.logger import log


class LoggingCursor(DictCursor):
    def execute(self, query, args=None):
        log.info(query % args if args else query)
        super().execute(query, args)

    def executemany(self, query, args=None):
        log.info(query % args if args else query)
        super().executemany(query, args)


class ConnectionPool:
    """https://gist.github.com/jeorgen/4eea9b9211bafeb18ada"""

    is_setup = False

    def setup(self):
        self.last_seen_process_id = os.getpid()
        self._init()
        self.is_setup = True

    def _init(self):
        self._pool = ThreadedConnectionPool(
            1,
            10,
            database=config.db_name,
            user=config.db_user,
            password=config.db_password,
            host=config.db_host,
            port=config.db_port,
            cursor_factory=LoggingCursor,
        )

    def getconn(self) -> connection:
        current_pid = os.getpid()
        if not (current_pid == self.last_seen_process_id):
            self._init()
            log.debug(
                f"New id is {current_pid}, old id was {self.last_seen_process_id}"
            )
            self.last_seen_process_id = current_pid
        db_connection = self._pool.getconn()
        return db_connection

    def putconn(self, conn: connection):
        return self._pool.putconn(conn)

    def closeall(self):
        self._pool.closeall()

    @contextmanager
    def get_db_connection(self) -> t.Generator[connection, None, None]:
        try:
            connection = self.getconn()
            yield connection
        finally:
            self.putconn(connection)

    @contextmanager
    def get_db_cursor(self, commit=False) -> t.Generator[LoggingCursor, None, None]:
        with self.get_db_connection() as connection:
            cursor = connection.cursor(cursor_factory=LoggingCursor)
            try:
                yield cursor
                if commit:
                    connection.commit()
            finally:
                cursor.close()


def connect_to_database() -> connection:
    log.info("Connecting to db")
    db_connection = psycopg2.connect(
        dbname=config.db_name,
        user=config.db_user,
        password=config.db_password,
        host=config.db_host,
        port=config.db_port,
        cursor_factory=LoggingCursor,
    )
    return db_connection


def close_database_connection(db_connection: connection) -> None:
    db_connection.close()


class MSN:
    def __init__(self):
        self.db = connect_to_database()

    def main(self, cursor):
        for fname in os.listdir(os.path.join(config.home, "data", "logs")):
            if not fname.lower().endswith(".xml"):
                continue

            log.info(fname)
            for message_data in MSN.parse_log(fname):
                MSN.add_entry(cursor, *message_data)

        self.db.commit()

    @staticmethod
    def parse_log(fname):
        with open(
            os.path.join(config.home, "data", "logs", fname), encoding="utf8"
        ) as infile:
            txt = infile.read()
        obj = parseString(
            txt.replace(b"\x1f".decode(), " ")
            .replace(b"\x02".decode(), " ")
            .replace(b"\x03".decode(), " ")
            .replace(b"\x04".decode(), " ")
            .replace(b"\x05".decode(), "|")
        )
        for message in obj.getElementsByTagName("Message") + obj.getElementsByTagName(
            "Invitation"
        ):
            msg_type = message.tagName.lower()
            msg_time = dt.datetime.strptime(
                message.getAttribute("DateTime"), "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            msg_source = fname
            session_ID = msg_source + message.getAttribute("SessionID")

            from_node = message.getElementsByTagName("From")[0]
            user_from_node = from_node.getElementsByTagName("User")[0]
            from_user = user_from_node.getAttribute("FriendlyName")
            participants = set([user_from_node.getAttribute("LogonName")])

            text_node = message.getElementsByTagName("Text")[0]
            msg_text = text_node.firstChild.nodeValue
            match = re.search(r"color:(#\w{6})", text_node.getAttribute("Style"))
            msg_color = match.group(1) if match else None

            if msg_type == "message":
                to_node = message.getElementsByTagName("To")[0]
                user_to_nodes = to_node.getElementsByTagName("User")
                to_users = [node.getAttribute("FriendlyName") for node in user_to_nodes]
                participants.update(
                    node.getAttribute("LogonName") for node in user_to_nodes
                )
            elif msg_type == "invitation":
                to_users = None

            if not all(
                participant in config.gargling_msn_emails
                for participant in participants
            ):
                continue

            yield (
                session_ID,
                msg_type,
                msg_time,
                msg_source,
                msg_color,
                from_user,
                to_users,
                msg_text,
            )

    @staticmethod
    def add_entry(
        cursor,
        session_ID,
        msg_type,
        msg_time,
        msg_source,
        msg_color,
        from_user,
        to_users,
        msg_text,
    ):
        sql_command = (
            "INSERT INTO msn_messages (session_ID, msg_type, msg_source, "
            "msg_time, from_user, to_users, msg_text, msg_color) "
            "VALUES (%(session_ID)s, %(msg_type)s, %(msg_source)s, %(msg_time)s,"
            "%(from_user)s, %(to_users)s, %(msg_text)s, %(msg_color)s);"
        )
        data = {
            "session_ID": session_ID,
            "msg_type": msg_type,
            "msg_time": msg_time,
            "msg_source": msg_source,
            "msg_color": msg_color,
            "from_user": from_user,
            "to_users": str(to_users),
            "msg_text": msg_text,
        }
        cursor.execute(sql_command, data)

    @staticmethod
    def add_user_ids_to_msn():
        db = connect_to_database()

        cursor = db.cursor()
        sql_command = "SELECT slack_nick, db_id FROM user_ids"
        cursor.execute(sql_command)
        users = cursor.fetchall()
        for slack_nick, db_id in users:
            msn_nicks = config.slack_to_msn_nicks[slack_nick]
            for msn_nick in msn_nicks:
                sql_command = (
                    f"UPDATE msn_messages SET db_id = {db_id} "
                    f'WHERE from_user LIKE "%{msn_nick}%"'
                )
                cursor.execute(sql_command)
        db.commit()
        db.close()


def add_user_ids_table():
    db = connect_to_database()
    users = []
    cursor = db.cursor()
    for slack_id, db_id, slack_nick, first_name in users:
        sql_command = (
            "INSERT INTO user_ids (db_id, slack_id, slack_nick, first_name) "
            "VALUES (%(db_id)s, %(slack_id)s, %(slack_nick)s, %(first_name)s)"
        )
        data = {
            "slack_nick": slack_nick,
            "slack_id": slack_id,
            "db_id": db_id,
            "first_name": first_name,
        }
        cursor.execute(sql_command, data)
    db.commit()
    db.close()


class DropPics:
    def __init__(self):
        self.db = None
        self.dbx = None
        self._firstname_to_db_id = None

    @property
    def firstname_to_db_id(self):
        if self._firstname_to_db_id is None:
            cursor = self.db.cursor()
            sql_command = "SELECT first_name, db_id FROM user_ids"
            cursor.execute(sql_command)
            self._firstname_to_db_id = {
                row["first_name"]: row["db_id"] for row in cursor.fetchall()
            }
        return self._firstname_to_db_id

    def connect_to_database(self):
        self.db = connect_to_database()

    def connect_dbx(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        log.info("Connected to dbx")

    @staticmethod
    def get_tags(image: t.Union[Path, str]) -> t.Optional[t.List[str]]:
        im = Image.open(image)
        exif = im._getexif()
        try:
            return exif[40094].decode("utf-16").rstrip("\x00").split(";")
        except KeyError:
            return None

    @staticmethod
    def get_date_taken(image: t.Union[Path, str]) -> dt.datetime:
        im = Image.open(image)
        exif = im._getexif()
        date_str = exif[36867]
        date_obj = dt.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        return date_obj

    def add_faces_in_pic(self, cursor: LoggingCursor, pic: Path, dbx_path: str):
        sql_command = "SELECT pic_id FROM dbx_pictures WHERE path = %(path)s"
        data = {"path": dbx_path}
        cursor.execute(sql_command, data)
        try:
            pic_id = cursor.fetchone()["pic_id"]
        except KeyError:
            log.info(f"pic not in db: {dbx_path}")
            return

        sql_command = "SELECT * FROM dbx_pictures_faces WHERE pic_id = %(pic_id)s"
        data = {"pic_id": pic_id}
        cursor.execute(sql_command, data)
        result = cursor.fetchone()
        if result is not None:
            log.info(f"{dbx_path} pic faces already in db with id {pic_id}")
            return

        tags = DropPics.get_tags(pic)
        if tags is None:
            return
        faces = set(tags).intersection(self.firstname_to_db_id)
        for face in faces:
            db_id = self.firstname_to_db_id[face]
            sql_command = (
                "INSERT INTO dbx_pictures_faces (db_id, pic_id) "
                "VALUES (%(db_id)s, %(pic_id)s);"
            )
            data = {"db_id": db_id, "pic_id": pic_id}
            cursor.execute(sql_command, data)

    def add_pics_in_folder(self, folder: Path, topic: str, dbx_folder: str) -> None:
        cursor = self.db.cursor()
        for pic in folder.iterdir():
            if not pic.suffix.lower() in {".jpg", ".jpeg"}:
                continue
            dbx_path = dbx_folder + "/" + pic.name.lower()

            sql_command = "SELECT pic_id FROM dbx_pictures WHERE path = %(path)s"
            data = {"path": dbx_path}
            cursor.execute(sql_command, data)
            if cursor.fetchone() is not None:
                log.info(f"{dbx_path} pic already in db")
                continue

            date_obj = DropPics.get_date_taken(pic)
            timestr = date_obj.strftime("%Y-%m-%d %H:%M:%S")

            sql_command = """INSERT INTO dbx_pictures (path, topic, taken)
            VALUES (%(path)s,
                   %(topic)s,
                   %(taken)s);"""
            data = {"path": dbx_path, "topic": topic, "taken": timestr}
            cursor.execute(sql_command, data)

            self.add_faces_in_pic(cursor, pic, dbx_path)
        self.db.commit()

    def add_faces_to_existing_pics(self, folder: Path, dbx_folder: str):
        self.connect_to_database()
        try:
            for pic in list(folder.iterdir()):
                dbx_path = dbx_folder + "/" + pic.name.lower()
                with self.db.cursor() as cursor:
                    self.add_faces_in_pic(cursor, pic, dbx_path)
        finally:
            self.db.commit()
            self.db.close()
