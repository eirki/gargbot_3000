#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import datetime as dt
import itertools
import typing as t

import aiosql
from dropbox import Dropbox
from psycopg2.extensions import connection

from gargbot_3000 import config
from gargbot_3000.database import JinjaSqlAdapter
from gargbot_3000.logger import log

queries = aiosql.from_path("sql/picture.sql", driver_adapter=JinjaSqlAdapter)


def connect_dbx() -> Dropbox:
    dbx = Dropbox(config.dropbox_token)
    log.info("Connected to dbx")
    return dbx


def sortout_args(
    args: t.Set[str],
    topic: t.Optional[str],
    year: t.Optional[str],
    garglings: list[str],
    exclusive: bool,
) -> t.Tuple[list, set]:
    valid_args = []
    if topic:
        valid_args.append(topic)
    if year:
        valid_args.append(year)
    if exclusive:
        valid_args.append("kun")
    valid_args.extend(garglings)
    invalid_args = args - set(valid_args)
    return valid_args, invalid_args


def reduce_arg_combinations(args: list[str]) -> t.Iterator[t.Sequence[str]]:
    try:
        args.remove("kun")
        yield args
    except ValueError:
        pass
    for length in reversed(range(1, len(args))):
        for arg_combination in itertools.combinations(args, length):
            yield arg_combination


def get_description_for_invalid_args(
    invalid_args: t.Set[str], years: list[str], topics: list[str], garglings: list[str],
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


def get_url_for_dbx_path(dbx: Dropbox, path: str):
    full_path = "/".join([config.dbx_pic_folder, path])
    log.info(f"Getting url for {full_path}")
    response = dbx.sharing_create_shared_link(full_path)
    url = response.url.replace("?dl=0", "?raw=1")
    return url


def get_random_pic(conn: connection, dbx: Dropbox):
    result = queries.random_pic(conn)
    taken_at = result["taken_at"]
    url = get_url_for_dbx_path(dbx, path=result["path"])
    return url, taken_at


def get_pic(
    conn: connection, dbx: Dropbox, arg_list: t.Optional[list[str]]
) -> t.Tuple[str, dt.datetime, str]:
    description = ""

    if not arg_list:
        url, taken_at = get_random_pic(conn, dbx)
        return url, taken_at, description

    args = {arg.lower() for arg in arg_list}
    parsed = queries.parse_args(conn, args=list(args))
    valid_args, invalid_args = sortout_args(args, **parsed)

    if invalid_args:
        all_args = queries.get_possible_args(conn)
        description = get_description_for_invalid_args(invalid_args, **all_args)
        if not valid_args:
            description += "Her er et tilfeldig bilde i stedet."
            url, taken_at = get_random_pic(conn, dbx)
            return url, taken_at, description

    data = queries.pic_for_topic_year_garglings(conn, **parsed)
    if data is not None:
        valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
        description += f"Her er et bilde med {valid_args_fmt}."
        path = data["path"]
        taken_at = data["taken_at"]
        url = get_url_for_dbx_path(dbx, path)
        return url, taken_at, description

    # No pics found for arg-combination. Reduce args until pic found
    valid_args_fmt = ", ".join(f"`{arg}`" for arg in valid_args)
    description += f"Fant ikke bilde med {valid_args_fmt}. "
    for arg_combination in reduce_arg_combinations(valid_args):
        log.info(f"arg_combination: {arg_combination}")
        parsed = queries.parse_args(conn, args=list(arg_combination))
        data = queries.pic_for_topic_year_garglings(conn, **parsed)
        if data is None:
            continue

        arg_combination_fmt = ", ".join(f"`{arg}`" for arg in arg_combination)
        description += f"Her er et bilde med {arg_combination_fmt} i stedet."
        taken_at = data["taken_at"]
        url = get_url_for_dbx_path(dbx, path=data["path"])
        return url, taken_at, description

    #  No pics found for any args
    url, taken_at = get_random_pic(conn, dbx)
    return url, taken_at, description
