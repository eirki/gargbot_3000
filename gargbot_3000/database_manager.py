#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

# Core
import os
from xml.dom.minidom import parseString
import datetime as dt
import re
import asyncio
import json
import traceback

# Dependencies
import MySQLdb
from MySQLdb.cursors import DictCursor
from PIL import Image
import dropbox

# Internal
from gargbot_3000 import config


class LoggingCursor(DictCursor):
    def execute(self, query, args=None):
        log.info(query % args if args else query)
        super().execute(query, args)

    def executemany(self, query, args=None):
        log.info(query % args if args else query)
        super().executemany(query, args)


def connect_to_database():
    connection = MySQLdb.connect(
        host=config.db_host,
        user=config.db_user,
        passwd=config.db_passwd,
        db=config.db_name,
        charset="utf8",
        cursorclass=LoggingCursor
    )
    return connection


def reconnect_if_disconnected(db_connection: MySQLdb.Connection):
    try:
        db_connection.ping()
    except MySQLdb.OperationalError:
        log.info("Database disconnected. Trying to reconnect")
        db_connection.ping(True)


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
        with open(os.path.join(config.home, "data", "logs", fname), encoding="utf8") as infile:
            txt = infile.read()
        obj = parseString(
            txt.replace(b"\x1f".decode(), " ")
               .replace(b"\x02".decode(), " ")
               .replace(b"\x03".decode(), " ")
               .replace(b"\x04".decode(), " ")
               .replace(b"\x05".decode(), "|")
        )
        for message in obj.getElementsByTagName("Message") + obj.getElementsByTagName("Invitation"):
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
                participants.update(node.getAttribute("LogonName") for node in user_to_nodes)
            elif msg_type == "invitation":
                to_users = None

            if not all(participant in config.gargling_msn_emails for participant in participants):
                continue

            yield (session_ID, msg_type, msg_time, msg_source,
                   msg_color, from_user, to_users, msg_text)

    @staticmethod
    def add_entry(cursor, session_ID, msg_type, msg_time, msg_source,
                  msg_color, from_user, to_users, msg_text):
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
            "msg_text": msg_text
        }
        cursor.execute(sql_command, data)


class DropPics:
    def connect_to_database(self):
        self.db = connect_to_database()

    def connect_dbx(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        log.info("Connected to dbx")

    def main(self):
        self.check_relevant_imgs()

        cursor = self.db.cursor()
        for topic, paths in self.paths.items():
            for path in paths:
                self.add_entry(path, topic, cursor)

        self.db.commit()

    @staticmethod
    def add_entry(path, topic, cursor):
        sql_command = """INSERT INTO dbx_pictures (path, topic)
        VALUES (%(path)s,
               %(topic)s);"""
        data = {
            "path": path,
            "topic": topic
        }
        cursor.execute(sql_command, data)

    def dbx_file_path_generator(self, dir):
        query = self.dbx.files_list_folder(dir, recursive=True)
        while True:
            for entry in query.entries:
                yield entry
            if not query.has_more:
                break
            query = self.dbx.files_list_folder_continue(query.cursor)

    def get_topics(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT topic FROM dbx_pictures")
        return [topic[0] for topic in cursor.fetchall()]

    def check_relevant_imgs(self):
        self.topics = self.get_topics()

        self.paths = {topic: [] for topic in self.topics}

        loop = asyncio.get_event_loop()
        tasks = [loop.create_task(self.check_relevance(entry, loop))
                 for entry in self.dbx_file_path_generator(config.kamera_paths)]

        loop.run_until_complete(asyncio.wait(tasks))
        loop.close()

    async def check_relevance(self, entry, loop):
        if not entry.path_lower.endswith(".jpg"):
            return
        metadata, response = await loop.run_in_executor(
            None, self.dbx.files_download, entry.path_lower
        )
        tag = DropPics.get_tag(response.raw)
        if not tag:
            return
        for topic, pathlist in self.paths.items():
            if topic in tag:
                pathlist.append(entry.path_lower)

    @staticmethod
    def get_tag(fileobject):
        im = Image.open(fileobject)
        exif = im._getexif()
        return exif[40094].decode("utf-16").rstrip("\x00")

    def get_date_taken(self, path):
        im = Image.open(path)
        exif = im._getexif()
        date_str = exif[36867]
        date_obj = dt.datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
        return date_obj

    def add_date_to_db_pics(self):
        sql = f'SELECT pic_id, path FROM dbx_pictures where taken IS NULL'
        cursor = self.db.cursor()
        cursor.execute(sql)
        all_pics = cursor.fetchall()
        log.info(len(all_pics))
        errors = []
        for pic_id, path in all_pics:
            try:
                log.info(path)
                md = self.dbx.files_get_metadata(path, include_media_info=True)
                date_obj = md.media_info.get_metadata().time_taken
                timestr = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                sql_command = "UPDATE dbx_pictures SET taken = %(timestr)s WHERE pic_id = %(pic_id)s"
                data = {
                    "timestr": timestr,
                    "pic_id": pic_id
                }

                cursor.execute(sql_command, data)
            except Exception as exc:
                errors.append([pic_id, path, exc])
                traceback.log.info_exc()
        self.db.commit()
        if errors:
            log.info("ERRORS:")
            log.info(errors)

    def add_new_pics(self, folder, topic, root):
        cursor = self.db.cursor()
        for pic in os.listdir(folder):
            if not pic.endswith((".jpg", ".jpeg")):
                continue
            disk_path = os.path.join(folder, pic)
            db_path = "/".join([root, pic.lower()])

            date_obj = self.get_date_taken(disk_path)
            timestr = date_obj.strftime('%Y-%m-%d %H:%M:%S')

            sql_command = """INSERT INTO dbx_pictures (path, topic, taken)
            VALUES (%(path)s,
                   %(topic)s,
                   %(taken)s);"""
            data = {
                "path": db_path,
                "topic": topic,
                "taken": timestr
            }
            cursor.execute(sql_command, data)
        self.db.commit()

    def add_faces(self):
        cursor = self.db.cursor()
        for garg_id, slack_nick in config.garg_ids_to_slack_nicks.items():
            sql_command = """INSERT INTO faces (garg_id, name)
            VALUES (%(garg_id)s,
                   %(name)s);"""
            data = {
                "garg_id": garg_id,
                "name": slack_nick,
            }
            cursor.execute(sql_command, data)
        self.db.commit()

    def add_faces_pics(self):
        with open(os.path.join(config.home, "data", "garg_faces all.json")) as j:
            all_faces = json.load(j)

        cursor = self.db.cursor()

        for path, faces in all_faces.items():
            sql_command = 'SELECT pic_id FROM dbx_pictures WHERE path = %(path)s'
            data = {"path": path}
            cursor.execute(sql_command, data)
            try:
                pic_id = cursor.fetchone()[0]
            except TypeError:
                log.info(f"pic not in db: {path}")
                continue
            for face in faces:
                garg_id = config.slack_nicks_to_garg_ids[face]
                sql_command = (
                    "INSERT INTO dbx_pictures_faces (garg_id, pic_id)"
                    "VALUES (%(garg_id)s, %(pic_id)s);"
                )
                data = {
                    "garg_id": garg_id,
                    "pic_id": pic_id,
                }
                cursor.execute(sql_command, data)
        self.db.commit()


def add_user_ids_table():
    db = connect_to_database()
    users = [
    ]
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
            "first_name": first_name
        }
        cursor.execute(sql_command, data)
    db.commit()
    db.close()

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

# add_user_ids_to_msn()
