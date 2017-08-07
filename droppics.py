#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
import time

import dropbox

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


if __name__ == "__main__":
    db_connection = config.connect_to_database()
    drop_pics = DropPics(db=db_connection)
    drop_pics.connect_dbx()
    # drop_pics.db_setup()
    try:
        for topic in drop_pics.topics:
            log.info(drop_pics.get_pic(topic))
        log.info(drop_pics.get_pic())
    finally:
        db_connection.close()
