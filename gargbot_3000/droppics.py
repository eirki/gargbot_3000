#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import itertools
import typing as t

import aiosql
import dropbox
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.database_manager import JinjaSqlAdapter
from gargbot_3000.logger import log

queries = aiosql.from_path("schema/dbx_pictures.sql", driver_adapter=JinjaSqlAdapter)


class DropPics:
    def __init__(self) -> None:
        self._connect_dbx()

    def _connect_dbx(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        log.info("Connected to dbx")

    def sortout_args(
        self,
        args: t.Set[str],
        topic: t.Optional[str],
        year: t.Optional[str],
        users: t.List[str],
    ) -> t.Tuple[set, set]:
        valid_args = set()
        if topic:
            valid_args.add(topic)
        if year:
            valid_args.add(year)
        for db_id, slack_nick in users:
            valid_args.add(slack_nick)
        invalid_args = args - valid_args
        return valid_args, invalid_args

    def get_description_for_invalid_args(
        self,
        invalid_args: t.Set[str],
        years: t.List[str],
        topics: t.List[str],
        users: t.List[str],
    ):
        invalid_args_fmt = ", ".join(f"`{arg}`" for arg in invalid_args)
        years_fmt = ", ".join(f"`{year}`" for year in years)
        topics_fmt = ", ".join(f"`{topic}`" for topic in topics)
        users_fmt = ", ".join(f"`{user}`" for user in users)
        description = (
            f"Im so stoopid! Skjønte ikke {invalid_args_fmt}. =( Jeg skjønner bare "
            f"\n*år*: {years_fmt};\n"
            f"*emner*: {topics_fmt};\n"
            f"samt *garlings* - husk å bruke slack nick: {users_fmt}\n"
        )
        return description

    def get_url_for_dbx_path(self, path: str):
        full_path = "/".join([config.dbx_pic_folder, path])
        log.info(f"Getting url for {full_path}")
        response = self.dbx.sharing_create_shared_link(full_path)
        url = response.url.replace("?dl=0", "?raw=1")
        return url

    def get_random_pic(self, conn: connection):
        result = queries.random_pic(conn)
        date_taken = result["taken"]
        url = self.get_url_for_dbx_path(path=result["path"])
        return url, date_taken

    def get_pic(
        self, db: connection, arg_list: t.Optional[t.List[str]]
    ) -> t.Tuple[str, dt.datetime, str]:
        description = ""

        if not arg_list:
            url, date_taken = self.get_random_pic(db)
            return url, date_taken, description

        args = {arg.lower() for arg in arg_list}
        parsed = queries.parse_args(db, args=list(args))
        valid_args, invalid_args = self.sortout_args(args, **parsed)

        if invalid_args:
            all_args = queries.get_possible_args(db)
            description = self.get_description_for_invalid_args(
                invalid_args, **all_args
            )
            if not valid_args:
                description += "Her er et tilfeldig bilde i stedet."
                url, date_taken = self.get_random_pic(db)
                return url, date_taken, description

        db_data = queries.pic_for_topic_year_users(db, **parsed)
        if db_data is not None:
            valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
            description += f"Her er et bilde med {valid_args_fmt}."
            path = db_data["path"]
            date_taken = db_data["taken"]
            url = self.get_url_for_dbx_path(path)
            return url, date_taken, description

        # No pics found for arg-combination. Reduce args until pic found
        valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
        description += f"Fant ikke bilde med {valid_args_fmt}. "
        for length in reversed(range(1, len(valid_args))):
            for arg_combination in itertools.combinations(valid_args, length):
                log.info(f"arg_combination: {arg_combination}")
                parsed = queries.parse_args(db, args=list(arg_combination))
                db_data = queries.pic_for_topic_year_users(db, **parsed)
                if db_data is None:
                    continue

                arg_combination_fmt = ", ".join(f"`{arg}`" for arg in arg_combination)
                description += f"Her er et bilde med {arg_combination_fmt} i stedet."
                date_taken = db_data["taken"]
                url = self.get_url_for_dbx_path(path=db_data["path"])
                return url, date_taken, description

        #  No pics found for any args
        url, date_taken = self.get_random_pic(db)
        return url, date_taken, description
