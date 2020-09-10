#! /usr/bin/env python3
# coding: utf-8
import typing as t

import aiosql
import pendulum
from psycopg2.extensions import connection

queries = aiosql.from_path("sql/journey_achievements.sql", "psycopg2")


def format_new(
    desc: str,
    unit: str,
    holders: t.Optional[t.List[int]],
    value: int,
    prev_holders: t.Optional[t.Set[int]],
    prev_value: t.Optional[int],
    gargling_info: t.Dict[int, dict],
):
    tangering = prev_value is None
    achv_txt = ""
    medal = ":first_place_medal:" if not tangering else ":sports_medal:"
    if holders is not None:
        names = [gargling_info[id_]["first_name"] for id_ in holders]
        achv_txt += f" {medal} og ".join(names)
    else:
        achv_txt += "Vi"
    achv_txt += f" {medal}"
    achv_txt += " har"
    if not tangering:
        achv_txt += f" satt ny rekord: {desc}, med {value} {unit}!"
    else:
        achv_txt += f" tangert rekord: {desc} ({value} {unit})!"
    if prev_holders is not None:
        names = [gargling_info[id_]["first_name"] for id_ in prev_holders]
        plural = "s" if len(prev_holders) > 1 else ""
        achv_txt += f" Forrige record holder{plural} var " + " og ".join(names)
        if not tangering:
            achv_txt += f", med {prev_value} {unit}"
    elif not tangering:
        achv_txt += f" Forrige rekord var {prev_value} {unit}"
    achv_txt += "."
    achv_txt += " Huzzah! :sonic:"
    return achv_txt


def extract(
    conn: connection,
    journey_id: int,
    date: pendulum.Date,
    func: t.Callable,
    desc: str,
    unit: str,
) -> t.Optional[
    t.Tuple[
        str, str, t.Optional[t.List[int]], int, t.Optional[t.Set[int]], t.Optional[int],
    ]
]:
    current = func(conn, journey_id=journey_id, taken_before=date)
    if len(current) == 0:
        return None
    if not any(rec["taken_at"] == date for rec in current):
        return None
    new = [rec for rec in current if rec["taken_at"] == date]
    value = new[0]["amount"]
    try:
        holders: t.Optional[t.List[int]] = [r["gargling_id"] for r in new]
    except KeyError:
        holders = None
    prev = [rec for rec in current if rec["taken_at"] < date]
    if prev:
        prev_value = None
    else:
        prev = func(conn, journey_id=journey_id, taken_before=date.subtract(days=1))
        if not prev:
            return None
        prev_value = prev[0]["amount"]
    try:
        prev_holders: t.Optional[t.Set[int]] = {r["gargling_id"] for r in prev}
    except KeyError:
        prev_holders = None

    return desc, unit, holders, value, prev_holders, prev_value


def most_steps_one_day_individual(**kwargs):
    return extract(
        func=queries.most_steps_one_day_individual,
        desc="Flest skritt gått av en gargling på én dag",
        unit="skritt",
        **kwargs,
    )


def most_steps_one_day_collective(**kwargs):
    return extract(
        func=queries.most_steps_one_day_collective,
        desc="Flest skritt gått av hele gargen på én dag",
        unit="skritt",
        **kwargs,
    )


def highest_share(**kwargs):
    return extract(
        func=queries.highest_share,
        desc="Størst andel av dagens skritt",
        unit="%",
        **kwargs,
    )


def biggest_improvement_individual(**kwargs):
    return extract(
        func=queries.biggest_improvement_individual,
        desc="Størst improvement fra en dag til neste for en gargling",
        unit="skritt",
        **kwargs,
    )


def biggest_improvement_collective(**kwargs):
    return extract(
        func=queries.biggest_improvement_collective,
        desc="Størst improvement fra en dag til neste for hele gargen",
        unit="skritt",
        **kwargs,
    )


def longest_streak(**kwargs):
    return extract(
        func=queries.longest_streak,
        desc="Lengste streak med førsteplasser",
        unit="dager",
        **kwargs,
    )


def new(
    conn: connection,
    journey_id: int,
    date: pendulum.Date,
    gargling_info: t.Dict[int, dict],
) -> t.Optional[str]:
    ordered = [
        most_steps_one_day_individual,
        most_steps_one_day_collective,
        longest_streak,
        highest_share,
        biggest_improvement_individual,
        biggest_improvement_collective,
    ]
    for achv_func in ordered:
        achv = achv_func(conn=conn, journey_id=journey_id, date=date)
        if achv is None:
            continue
        desc, unit, holders, value, prev_holders, prev_value = achv
        formatted = format_new(
            desc, unit, holders, value, prev_holders, prev_value, gargling_info
        )
        return formatted
    return None


def current(conn):
    ...
