#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
import time
import re
import itertools

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

    def get_pic(self, *args):
        print(args)

        path = None
        cursor = self.db.cursor()
        if args:

            sql_filter = []
            data = {}

            topic = next((topic for topic in self.topics if topic in args), None)
            if topic:
                sql_filter.append("p.topic = %(topic)s")
                data["topic"] = topic

            year = next((word for word in args if re.match(r"\d\d\d\d", word)), None)
            if year:
                sql_filter.append("YEAR(p.taken) = %(year)s")
                data["year"] = year

            for user, garg_id in config.slack_nicks_to_garg_ids.items():
                if user in args:
                    sql_filter.append("f.garg_id = %(garg_id)s")
                    data["garg_id"] = garg_id
                    join = 'LEFT JOIN dbx_pictures_faces as f ON p.pic_id = f.pic_id'
                    break
            else:
                join = ""

            if sql_filter:
                sql_filter = "WHERE " + " AND ".join(sql_filter)

            sql_command = (
                'SELECT p.path, p.taken FROM dbx_pictures as p '
                f'{join} {sql_filter} ORDER BY RAND() LIMIT 1'
            )
            log.info(sql_command)
            log.info(sql_command % data)
            cursor.execute(sql_command, data)
            try:
                path, date_obj = cursor.fetchone()
                pic_random = False
            except:
                print("No picture found with those attributes. Here's a random picture")

        if path is None:
            sql_command = (
                'SELECT path, taken FROM dbx_pictures '
                'WHERE topic = %(topic)s ORDER BY RAND() LIMIT 1'
            )
            data = {"topic": random.choice(self.topics)}
            pic_random = True

            log.info(sql_command % data)
            cursor.execute(sql_command, data)
            path, date_obj = cursor.fetchone()

        timestamp = int(time.mktime(date_obj.timetuple()))

        response = self.dbx.sharing_create_shared_link(path)
        url = response.url.replace("?dl=0", "?raw=1")
        return url, timestamp, pic_random


if __name__ == "__main__":
    db_connection = config.connect_to_database()
    drop_pics = DropPics(db=db_connection)
    drop_pics.connect_dbx()
    # drop_pics.db_setup()
    try:
        log.info(drop_pics.get_pic())

        topics = drop_pics.topics[:]
        for topic in topics[0:2]:
            log.info(drop_pics.get_pic(topic))

        years = [str(year) for year in range(2005, 2018)]
        for year in years[0:2]:
            log.info(drop_pics.get_pic(year))

        users = list(config.slack_nicks_to_garg_ids.keys())
        for user in users[0:2]:
            log.info(drop_pics.get_pic(user))

        all_args = [topics, years, users]
        for permutation in list(itertools.product(*all_args),)[0:2]:
            log.info(drop_pics.get_pic(*permutation))

    finally:
        db_connection.close()
