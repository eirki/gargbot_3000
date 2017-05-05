#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
import json
import os
import asyncio
import time

import dropbox
from PIL import Image

import config


class DropPics:
    topics = ["lark", "fe", "skating", "henging", "spillnight"]

    def __init__(self, db):
        self.db = db

    def connect_dbx(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        log.info("Connected to dbx")

    def get_pic(self, topic=None):
        if topic is None:
            topic = random.choice(self.topics)
        sql = f'SELECT path FROM dbx_pictures WHERE topic = "{topic}" ORDER BY RAND() LIMIT 1'
        log.info(sql)
        cursor = self.db.cursor()
        cursor.execute(sql)
        path = cursor.fetchone()[0]

        md = self.dbx.files_get_metadata(path, include_media_info=True)
        date_obj = md.media_info.get_metadata().time_taken
        timestamp = int(time.mktime(date_obj.timetuple()))

        response = self.dbx.sharing_create_shared_link(path)
        url = response.url.replace("?dl=0", "?raw=1")
        return url, timestamp

    def db_setup(self):
        self.check_relevant_imgs()

        cursor = self.db.cursor()
        cursor.execute("DROP TABLE IF EXISTS dbx_pictures")
        sql_command = """
        CREATE TABLE dbx_pictures (
        path CHAR(100),
        topic CHAR(30));
        """
        cursor.execute(sql_command)

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

    def db_file_path_generator(self, dir):
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
                 for entry in self.db_file_path_generator(config.kamera_paths)]

        loop.run_until_complete(asyncio.wait(tasks))
        loop.close()

    async def check_relevance(self, entry, loop):
        if not entry.path_lower.endswith(".jpg"):
            return
        metadata, response = await loop.run_in_executor(None, self.dbx.files_download, entry.path_lower)
        tag = get_tag(response.raw)
        if not tag:
            return
        elif "Forsterka Enhet" in tag:
            self.paths["fe"].append(entry.path_lower)
        elif "Skating" in tag:
            self.paths["skate"].append(entry.path_lower)
        elif "Larkollen" in tag:
            self.paths["lark"].append(entry.path_lower)


def get_tag(fileobject):
    im = Image.open(fileobject)
    exif = im._getexif()
    return exif[40094].decode("utf-16").rstrip("\x00")


if __name__ == "__main__":
    db_connection = config.connect_to_database()
    drop_pics = DropPics(db=db_connection)
    drop_pics.connect()
    # drop_pics.db_setup()
    try:
        for topic in drop_pics.topics:
            log.info(drop_pics.get_pic(topic))
        log.info(drop_pics.get_pic())
    finally:
        db_connection.close()
