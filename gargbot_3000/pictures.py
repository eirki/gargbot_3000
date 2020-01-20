#! /usr/bin/env python3.6
# coding: utf-8
import datetime as dt
import itertools
import typing as t

import aiosql
import dropbox
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.database import JinjaSqlAdapter
from gargbot_3000.logger import log

queries = aiosql.from_path("sql/picture.sql", driver_adapter=JinjaSqlAdapter)


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
        garglings: t.List[str],
    ) -> t.Tuple[set, set]:
        valid_args = set()
        if topic:
            valid_args.add(topic)
        if year:
            valid_args.add(year)
        for gargling_id, slack_nick in garglings:
            valid_args.add(slack_nick)
        invalid_args = args - valid_args
        return valid_args, invalid_args

    def get_description_for_invalid_args(
        self,
        invalid_args: t.Set[str],
        years: t.List[str],
        topics: t.List[str],
        garglings: t.List[str],
    ):
        invalid_args_fmt = ", ".join(f"`{arg}`" for arg in invalid_args)
        years_fmt = ", ".join(f"`{year}`" for year in years)
        topics_fmt = ", ".join(f"`{topic}`" for topic in topics)
        garglings_fmt = ", ".join(f"`{gargling}`" for gargling in garglings)
        description = (
            f"Im so stoopid! Skjønte ikke {invalid_args_fmt}. =( Jeg skjønner bare "
            f"\n*år*: {years_fmt};\n"
            f"*emner*: {topics_fmt};\n"
            f"samt *garlings* - husk å bruke slack nick: {garglings_fmt}\n"
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
        taken_at = result["taken_at"]
        url = self.get_url_for_dbx_path(path=result["path"])
        return url, taken_at

    def get_pic(
        self, conn: connection, arg_list: t.Optional[t.List[str]]
    ) -> t.Tuple[str, dt.datetime, str]:
        description = ""

        if not arg_list:
            url, taken_at = self.get_random_pic(conn)
            return url, taken_at, description

        args = {arg.lower() for arg in arg_list}
        parsed = queries.parse_args(conn, args=list(args))
        valid_args, invalid_args = self.sortout_args(args, **parsed)

        if invalid_args:
            all_args = queries.get_possible_args(conn)
            description = self.get_description_for_invalid_args(
                invalid_args, **all_args
            )
            if not valid_args:
                description += "Her er et tilfeldig bilde i stedet."
                url, taken_at = self.get_random_pic(conn)
                return url, taken_at, description

        data = queries.pic_for_topic_year_garglings(conn, **parsed)
        if data is not None:
            valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
            description += f"Her er et bilde med {valid_args_fmt}."
            path = data["path"]
            taken_at = data["taken_at"]
            url = self.get_url_for_dbx_path(path)
            return url, taken_at, description

        # No pics found for arg-combination. Reduce args until pic found
        valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
        description += f"Fant ikke bilde med {valid_args_fmt}. "
        for length in reversed(range(1, len(valid_args))):
            for arg_combination in itertools.combinations(valid_args, length):
                log.info(f"arg_combination: {arg_combination}")
                parsed = queries.parse_args(conn, args=list(arg_combination))
                data = queries.pic_for_topic_year_garglings(conn, **parsed)
                if data is None:
                    continue

                arg_combination_fmt = ", ".join(f"`{arg}`" for arg in arg_combination)
                description += f"Her er et bilde med {arg_combination_fmt} i stedet."
                taken_at = data["taken_at"]
                url = self.get_url_for_dbx_path(path=data["path"])
                return url, taken_at, description

        #  No pics found for any args
        url, taken_at = self.get_random_pic(conn)
        return url, taken_at, description
