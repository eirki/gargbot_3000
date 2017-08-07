#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import os
from xml.dom.minidom import parseString
import datetime as dt
import re
import asyncio
import json
import traceback

from PIL import Image
import dropbox

import config


class MSN:
    def __init__(self):
        self.db = config.connect_to_database()

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
        try:
            cursor.execute(sql_command, data)
        except:
            print(sql_command % data)
            raise


class DropPics:
    def connect_to_database(self):
        self.db = config.connect_to_database()

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
        try:
            log.info(sql_command % data)
            cursor.execute(sql_command, data)
        except:
            raise

    def dbx_file_path_generator(self, dir):
        query = self.dbx.files_list_folder(dir, recursive=True)
        while True:
            for entry in query.entries:
                yield entry
            if not query.has_more:
                break
            query = self.dbx.files_list_folder_continue(query.cursor)

    def check_relevant_imgs(self):
        self.paths = {
            "skate": [],
            "fe": [],
            "lark": [],
        }

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
        elif "Forsterka Enhet" in tag:
            self.paths["fe"].append(entry.path_lower)
        elif "Skating" in tag:
            self.paths["skate"].append(entry.path_lower)
        elif "Larkollen" in tag:
            self.paths["lark"].append(entry.path_lower)

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
        print(len(all_pics))
        errors = []
        for pic_id, path in all_pics:
            try:
                print(path)
                md = self.dbx.files_get_metadata(path, include_media_info=True)
                date_obj = md.media_info.get_metadata().time_taken
                timestr = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                sql_command = "UPDATE dbx_pictures SET taken = %(timestr)s WHERE pic_id = %(pic_id)s"
                data = {
                    "timestr": timestr,
                    "pic_id": pic_id
                }

                log.info(sql_command % data)
                cursor.execute(sql_command, data)
            except Exception as exc:
                errors.append([pic_id, path, exc])
                traceback.print_exc()
        self.db.commit()
        if errors:
            print("ERRORS:")
            print(errors)

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
            print(sql_command % data)
            cursor.execute(sql_command, data)
        self.db.commit()

