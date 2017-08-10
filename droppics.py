#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
import time
import itertools
import contextlib
import dropbox

import config


class DropPics:

    def __init__(self, db):
        self.db = db
        cursor = self.db.cursor()
        self.years = self.get_years(cursor)
        self.topics = self.get_topics(cursor)
        self.possible_args = self.topics | self.years | set(config.slack_nicks_to_garg_ids.keys())

    def get_years(self, cursor):
        sql_command = "SELECT DISTINCT YEAR(taken) FROM dbx_pictures ORDER BY YEAR(taken)"
        log.info(sql_command)
        cursor.execute(sql_command)
        return set(str(year[0]) for year in cursor.fetchall())

    def get_topics(self, cursor):
        sql_command = "SELECT topic FROM dbx_pictures"
        log.info(sql_command)
        cursor.execute(sql_command)
        return set(topic[0] for topic in cursor.fetchall())

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
            garg_id = next(
                garg_id
                for user, garg_id in config.slack_nicks_to_garg_ids.items()
                if user in args
            )
            sql_filter.append("f.garg_id = %(garg_id)s")
            data["garg_id"] = garg_id
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

    def get_pic(self, *args):
        log.info(args)

        error_text = ""

        cursor = self.db.cursor()
        if args:
            args = set(args)
            invalid_args = args - self.possible_args
            valid_args = args - invalid_args
            if invalid_args:
                error_text = (
                    "Skjønte ikke '{invalid_args}'.\n"
                    "Jeg skjønner år: {years},\n"
                    "emner: {topics},\n"
                    "samt garlings - husk å bruke slack nick: {slack_nicks}\n"
                ).format(
                    invalid_args=", ".join(invalid_args),
                    years=", ".join(sorted(self.years)),
                    topics=", ".join(self.topics),
                    slack_nicks=", ".join(config.slack_nicks_to_garg_ids.keys()),
                )

            if valid_args:
                sql_command, data = self.get_sql_for_args(valid_args)

                log.info(sql_command % data)
                cursor.execute(sql_command, data)
                try:
                    path, date_obj = cursor.fetchone()
                    if invalid_args:
                        error_text += "Her er et bilde med '{}':".format(", ".join(valid_args))
                except TypeError:
                    error_text += (
                        "Fant ikke bilde med '{}'. "
                        "Her er et tilfeldig bilde i stedet:").format(", ".join(valid_args))
                else:

                    timestamp, url = self.get_timestamp_url(path, date_obj)
                    return url, timestamp, error_text
            else:
                error_text += "Her er et tilfeldig bilde i stedet:"

        sql_command = (
            'SELECT path, taken FROM dbx_pictures '
            'WHERE topic = %(topic)s ORDER BY RAND() LIMIT 1'
        )
        data = {"topic": random.choice(list(self.topics))}

        log.info(sql_command % data)
        cursor.execute(sql_command, data)
        path, date_obj = cursor.fetchone()

        timestamp, url = self.get_timestamp_url(path, date_obj)

        return url, timestamp, error_text

    def get_timestamp_url(self, path, date_obj):
        timestamp = int(time.mktime(date_obj.timetuple()))
        response = self.dbx.sharing_create_shared_link(path)
        url = response.url.replace("?dl=0", "?raw=1")
        return timestamp, url


if __name__ == "__main__":
    db_connection = config.connect_to_database()
    drop_pics = DropPics(db=db_connection)
    drop_pics.connect_dbx()
    # drop_pics.db_setup()
    try:
        log.info(drop_pics.get_pic(*[]))

        topics = list(drop_pics.topics)
        for topic in topics[0:2]:
            log.info(drop_pics.get_pic(*[topic]))

        years = list(drop_pics.years)
        for year in years[0:2]:
            log.info(drop_pics.get_pic(*[year]))

        users = list(config.slack_nicks_to_garg_ids.keys())
        for user in users[0:2]:
            log.info(drop_pics.get_pic(*[user]))

        all_args = [topics, years, users]
        for permutation in list(itertools.product(*all_args),)[0:2]:
            log.info(drop_pics.get_pic(*permutation))

        # Errors:
        log.info(drop_pics.get_pic(*["2000"]))

        log.info(drop_pics.get_pic(*["2000", users[0]]))
    finally:
        db_connection.close()
