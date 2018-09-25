#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

# Core
import random
import time
import contextlib
import itertools

# Dependencies
import dropbox

# Internal
from gargbot_3000 import config

# Typing
from typing import Set, Tuple, Optional, List, Iterable
from psycopg2.extensions import connection
import datetime as dt
from gargbot_3000.database_manager import LoggingCursor


class DropPics:
    def __init__(self, db: Optional[connection], run_setup: bool=True) -> None:
        self._connect_dbx()
        if run_setup:
            self.setup(db)

    def setup(self, db):
        cursor = db.cursor()
        self.years = self.get_years(cursor)
        self.topics = self.get_topics(cursor)
        self.users = self.get_users(cursor)
        self.possible_args = self.topics | self.years | set(self.users)

    def get_years(self, cursor: LoggingCursor):
        sql_command = "SELECT DISTINCT EXTRACT(YEAR FROM taken)::int as year FROM dbx_pictures ORDER BY year"
        cursor.execute(sql_command)
        years = set(str(row["year"]) for row in cursor.fetchall())
        return years

    def get_topics(self, cursor: LoggingCursor):
        sql_command = "SELECT DISTINCT topic FROM dbx_pictures"
        cursor.execute(sql_command)
        topics = set(row["topic"] for row in cursor.fetchall())
        return topics

    def get_users(self, cursor: LoggingCursor):
        sql_command = "SELECT slack_nick, db_id FROM user_ids"
        cursor.execute(sql_command)
        users = {row["slack_nick"]: row["db_id"] for row in cursor.fetchall()}
        return users

    def _connect_dbx(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        log.info("Connected to dbx")

    def get_description_for_invalid_args(self, invalid_args: Set[str]):
        invalid_args_fmt = ", ".join(f"`{arg}`" for arg in invalid_args)
        years_fmt = ", ".join(f"`{year}`" for year in sorted(self.years))
        topics_fmt = ", ".join(f"`{topic}`" for topic in self.topics)
        users_fmt = ", ".join(f"`{user}`" for user in self.users.keys())
        description = (
            f"Im so stoopid! Skjønte ikke {invalid_args_fmt}. =( Jeg skjønner bare "
            f"\n*år*: {years_fmt};\n"
            f"*emner*: {topics_fmt};\n"
            f"samt *garlings* - husk å bruke slack nick: {users_fmt}\n"
        )
        return description

    def get_sql_for_args(self, args: Iterable[str]):
        sql_filter = []
        sql_data = {}

        # topic arg
        with contextlib.suppress(StopIteration):
            topic = next(arg for arg in args if arg in self.topics)
            sql_filter.append("p.topic = %(topic)s")
            sql_data["topic"] = topic

        # year arg
        with contextlib.suppress(StopIteration):
            year = next(arg for arg in args if arg in self.years)
            sql_filter.append("EXTRACT(YEAR FROM p.taken)::int = %(year)s")
            sql_data["year"] = year

        # face arg(s)
        db_ids = [db_id for user, db_id in self.users.items() if user in args]
        if len(db_ids) == 0:
            join = ""
        elif len(db_ids) == 1:
            db_id = db_ids[0]
            sql_filter.append("f.db_id = %(db_id)s")
            sql_data["db_id"] = db_id
            join = "LEFT JOIN dbx_pictures_faces as f ON p.pic_id = f.pic_id"
        elif len(db_ids) > 1:
            join = (
                "LEFT JOIN (SELECT ARRAY_AGG(db_id) as db_ids, pic_id from dbx_pictures_faces "
                "group BY pic_id) as f ON p.pic_id = f.pic_id"
            )
            for db_id in db_ids:
                sql_filter.append(f"'%(db_id{db_id})s' = ANY(f.db_ids)")
                sql_data[f"db_id{db_id}"] = db_id

        sql_filter_str = "WHERE " + " AND ".join(sql_filter)
        sql_command = (
            "SELECT p.path, p.taken FROM dbx_pictures as p "
            f"{join} {sql_filter_str} ORDER BY RANDOM() LIMIT 1"
        )
        # print(sql_command % sql_data)
        # "SELECT p.path, p.taken FROM dbx_pictures as p LEFT JOIN (SELECT GROUP_CONCAT(db_id) as db_ids, pic_id from dbx_pictures_faces group BY pic_id) as f ON p.pic_id = f.pic_id WHERE FIND_IN_SET('3',f.db_ids) AND FIND_IN_SET('11',f.db_ids) ORDER BY RANDOM() LIMIT 1"
        return sql_command, sql_data

    def get_timestamp(self, date_obj: dt.datetime):
        return int(time.mktime(date_obj.timetuple()))

    def get_url_for_dbx_path(self, path: str):
        response = self.dbx.sharing_create_shared_link(path)
        url = response.url.replace("?dl=0", "?raw=1")
        return url

    def get_dbx_path_sql_cmd(
        self, cursor: LoggingCursor, sql_command: str, sql_data: dict
    ):
        cursor.execute(sql_command, sql_data)
        db_data = cursor.fetchone()
        return db_data

    def get_random_pic(self, cursor: LoggingCursor):
        sql_command = (
            "SELECT path, taken FROM dbx_pictures "
            "WHERE topic = %(topic)s ORDER BY RANDOM() LIMIT 1"
        )
        data = {"topic": random.choice(list(self.topics))}

        cursor.execute(sql_command, data)
        result = cursor.fetchone()
        path = result["path"]
        date_obj = result["taken"]
        url = self.get_url_for_dbx_path(path)
        timestamp = self.get_timestamp(date_obj)
        return url, timestamp

    def get_pic(self, db, arg_list: Optional[List[str]]) -> Tuple[str, int, str]:
        description = ""
        cursor = db.cursor()

        if not arg_list:
            url, timestamp = self.get_random_pic(cursor)
            return url, timestamp, description

        args = {arg.lower() for arg in arg_list}
        invalid_args = args - self.possible_args
        valid_args = args - invalid_args

        if invalid_args:
            description = self.get_description_for_invalid_args(invalid_args)
            if not valid_args:
                description += "Her er et tilfeldig bilde i stedet:"
                url, timestamp = self.get_random_pic(cursor)
                return url, timestamp, description

        sql_command, data = self.get_sql_for_args(valid_args)
        db_data = self.get_dbx_path_sql_cmd(cursor, sql_command, data)
        if db_data is not None:
            valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
            description += f"Her er et bilde med {valid_args_fmt}:"
            path = db_data["path"]
            date_obj = db_data["taken"]
            url = self.get_url_for_dbx_path(path)
            timestamp = self.get_timestamp(date_obj)
            return url, timestamp, description

        # No pics found for arg-combination. Reduce args until pic found
        valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
        description += f"Fant ikke bilde med {valid_args_fmt}. "
        for length in reversed(range(1, len(valid_args))):
            for arg_combination in itertools.combinations(valid_args, length):
                sql_command, data = self.get_sql_for_args(arg_combination)
                db_data = self.get_dbx_path_sql_cmd(cursor, sql_command, data)
                if db_data is None:
                    continue

                arg_combination_fmt = ", ".join(f"`{arg}`" for arg in arg_combination)
                description += f"Her er et bilde med {arg_combination_fmt} i stedet:"
                path = db_data["path"]
                date_obj = db_data["taken"]
                url = self.get_url_for_dbx_path(path)
                timestamp = self.get_timestamp(date_obj)
                return url, timestamp, description

        #  No pics found for any args
        url, timestamp = self.get_random_pic(cursor)
        return url, timestamp, description
