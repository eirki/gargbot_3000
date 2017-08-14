#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
import time
import contextlib
import dropbox

import config


class DropPics:
    def __init__(self, db):
        self.db = db
        cursor = self.db.cursor()
        self.years = self.get_years(cursor)
        self.topics = self.get_topics(cursor)
        self.users = self.get_users(cursor)
        self.possible_args = self.topics | self.years | set(self.users)

    def get_years(self, cursor):
        sql_command = "SELECT DISTINCT YEAR(taken) FROM dbx_pictures ORDER BY YEAR(taken)"
        cursor.execute(sql_command)
        return set(str(year[0]) for year in cursor.fetchall())

    def get_topics(self, cursor):
        sql_command = "SELECT topic FROM dbx_pictures"
        cursor.execute(sql_command)
        return set(topic[0] for topic in cursor.fetchall())

    def get_users(self, cursor):
        sql_command = "SELECT slack_nick, db_id FROM user_ids"
        cursor.execute(sql_command)
        return dict(cursor.fetchall())

    def connect_dbx(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        log.info("Connected to dbx")

    def get_sql_for_args(self, args):
        sql_filter = []
        data = {}

        with contextlib.suppress(StopIteration):
            topic = next(arg for arg in args if arg in self.topics)
            sql_filter.append("p.topic = %(topic)s")
            data["topic"] = topic

        with contextlib.suppress(StopIteration):
            year = next(arg for arg in args if arg in self.years)
            sql_filter.append("YEAR(p.taken) = %(year)s")
            data["year"] = year

        try:
            db_id = next(
                db_id
                for user, db_id in self.users.items()
                if user in args
            )
            sql_filter.append("f.db_id = %(db_id)s")
            data["db_id"] = db_id
            join = 'LEFT JOIN dbx_pictures_faces as f ON p.pic_id = f.pic_id'
        except StopIteration:
            join = ""

        if sql_filter:
            sql_filter = "WHERE " + " AND ".join(sql_filter)

        sql_command = (
            'SELECT p.path, p.taken FROM dbx_pictures as p '
            f'{join} {sql_filter} ORDER BY RAND() LIMIT 1'
        )
        return sql_command, data

    def get_timestamp(self, date_obj):
        return int(time.mktime(date_obj.timetuple()))

    def get_url(self, path):
        response = self.dbx.sharing_create_shared_link(path)
        url = response.url.replace("?dl=0", "?raw=1")
        return url

    def get_pic(self, *args):
        error_text = ""
        cursor = self.db.cursor()

        if args:
            args = set(args)
            invalid_args = args - self.possible_args
            valid_args = args - invalid_args
            if invalid_args:
                invalid_args_fmt = ", ".join(f"`{arg}`" for arg in invalid_args)
                years_fmt = ", ".join(f"`{year}`" for year in sorted(self.years))
                topics_fmt = ", ".join(f"`{topic}`" for topic in self.topics)
                slack_nicks_fmt = ", ".join(f"`{user}`" for user in
                                            self.users.keys())
                error_text = (
                    f"Im so stoopid! Skjønte ikke {invalid_args_fmt}. =( Jeg skjønner bare "
                    f"\n*år*: {years_fmt};\n"
                    f"*emner*: {topics_fmt};\n"
                    f"samt *garlings* - husk å bruke slack nick: {slack_nicks_fmt}\n"
                )

            if valid_args:
                sql_command, data = self.get_sql_for_args(valid_args)

                valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)

                cursor.execute(sql_command, data)
                data = cursor.fetchone()
                if data is not None:
                    path, date_obj = data
                    url = self.get_url(path)
                    timestamp = self.get_timestamp(date_obj)
                    if invalid_args:
                        error_text += f"Her er et bilde med {valid_args_fmt}:"
                    return url, timestamp, error_text
                else:
                    error_text += (
                        f"Fant ikke bilde med {valid_args_fmt}. "
                        "Her er et tilfeldig bilde i stedet:"
                    )
            else:
                error_text += "Her er et tilfeldig bilde i stedet:"

        sql_command = (
            'SELECT path, taken FROM dbx_pictures '
            'WHERE topic = %(topic)s ORDER BY RAND() LIMIT 1'
        )
        data = {"topic": random.choice(list(self.topics))}

        cursor.execute(sql_command, data)
        path, date_obj = cursor.fetchone()
        url = self.get_url(path)
        timestamp = self.get_timestamp(date_obj)

        return url, timestamp, error_text
