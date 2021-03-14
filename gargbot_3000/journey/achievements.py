#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import typing as t

import pendulum
from psycopg2.extensions import connection

from gargbot_3000.journey import common

queries = common.queries.achievements


possible = [
    {
        "query": queries.most_steps_one_day_individual,
        "emoji": ":first_place_medal:",
        "desc": "Flest skritt gått av en gargling på én dag",
        "unit": "skritt",
        "kwargs": {"less_than": None},
        "collective": False,
    },
    {
        "query": queries.most_steps_one_day_collective,
        "emoji": ":trophy:",
        "desc": "Flest skritt gått av hele gargen på én dag",
        "unit": "skritt",
        "collective": True,
    },
    {
        "query": queries.highest_share,
        "emoji": ":sports_medal:",
        "desc": "Størst andel av dagens skritt",
        "unit": "%",
        "collective": False,
    },
    {
        "query": queries.biggest_improvement_individual,
        "emoji": ":sports_medal:",
        "desc": "Størst improvement fra en dag til neste for en gargling",
        "unit": "skritt",
        "collective": False,
    },
    {
        "query": queries.biggest_improvement_collective,
        "emoji": ":trophy:",
        "desc": "Størst improvement fra en dag til neste for hele gargen",
        "unit": "skritt",
        "collective": True,
    },
    {
        "query": queries.longest_streak,
        "emoji": ":sports_medal:",
        "desc": "Lengste streak med førsteplasser",
        "unit": "dager",
        "collective": False,
    },
]


def format_new(
    desc: str,
    unit: str,
    holders: t.Optional[list[int]],
    value: int,
    prev_holders: t.Optional[t.Set[int]],
    prev_value: t.Optional[int],
    gargling_info: dict[int, dict],
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
    query: t.Callable,
    **query_kwargs,
) -> t.Optional[
    tuple[t.Optional[list[int]], int, t.Optional[t.Set[int]], t.Optional[int]]
]:
    current = query(conn, journey_id=journey_id, taken_before=date, **query_kwargs)
    if len(current) == 0:
        return None
    if not any(rec["taken_at"] == date for rec in current):
        return None
    new = [rec for rec in current if rec["taken_at"] == date]
    value = new[0]["amount"]
    try:
        holders: t.Optional[list[int]] = [r["gargling_id"] for r in new]
    except KeyError:
        holders = None
    prev = [rec for rec in current if rec["taken_at"] < date]
    if prev:
        prev_value = None
    else:
        prev = query(
            conn,
            journey_id=journey_id,
            taken_before=date.subtract(days=1),
            **query_kwargs,
        )
        if not prev:
            return None
        prev_value = prev[0]["amount"]
    try:
        prev_holders: t.Optional[t.Set[int]] = {r["gargling_id"] for r in prev}
    except KeyError:
        prev_holders = None
    return holders, value, prev_holders, prev_value


def new(
    conn: connection,
    journey_id: int,
    date: pendulum.Date,
    gargling_info: dict[int, dict],
) -> t.Optional[str]:
    for p in possible:
        achv = extract(
            conn=conn,
            journey_id=journey_id,
            date=date,
            query=p["query"],
            **p.get("kwargs", {}),
        )
        if achv is None:
            continue
        unit = p["unit"]
        desc = p["desc"]
        holders, value, prev_holders, prev_value = achv
        formatted = format_new(
            desc=desc,
            unit=unit,
            holders=holders,
            value=value,
            prev_holders=prev_holders,
            prev_value=prev_value,
            gargling_info=gargling_info,
        )
        return formatted
    return None


def get_all_at_date(conn, journey_id, date=None):
    all_records: list[dict] = []
    p = possible[0]
    most = [
        p,
        {
            "query": queries.most_steps_one_day_individual,
            "emoji": ":second_place_medal:",
            "desc": "Nest flest skritt gått av en gargling på én dag",
            "unit": "skritt",
            "collective": False,
        },
        {
            "query": queries.most_steps_one_day_individual,
            "emoji": ":third_place_medal:",
            "desc": "Tredje flest skritt gått av en gargling på én dag",
            "unit": "skritt",
            "collective": False,
        },
    ]
    less_than = None
    for p in most:
        query = p["query"]
        rec = query(conn, journey_id=journey_id, taken_before=date, less_than=less_than)
        if not rec:  # no test coverage
            break
        all_records.append(
            {
                "records": rec,
                "emoji": p["emoji"],
                "desc": p["desc"],
                "unit": p["unit"],
                "collective": p["collective"],
            }
        )
        less_than = rec[0]["amount"]

    for p in possible[1:]:
        query = p["query"]
        rec = query(conn, journey_id=journey_id, taken_before=date)
        if not rec:
            continue
        all_records.append(
            {
                "records": rec,
                "emoji": p["emoji"],
                "desc": p["desc"],
                "unit": p["unit"],
                "collective": p["collective"],
            }
        )
    return all_records


def format_all(gargling_info: dict[int, dict], records) -> str:
    def fdate(date: pendulum.Date) -> str:
        return f"{date.day}.{date.month}.{date.year}"

    def format_col(data) -> str:
        desc = data["desc"]
        amount = data["records"][0]["amount"]
        unit = data["unit"]
        res = f"{desc}: {amount} {unit} {data['emoji']} - "
        res += " & ".join([fdate(rec["taken_at"]) for rec in data["records"]])
        return res

    def format_ind(data) -> str:
        desc = data["desc"]
        amount = data["records"][0]["amount"]
        unit = data["unit"]
        res = f"{desc}: {amount} {unit} - "
        ppl = []
        for rec in data["records"]:
            name = gargling_info[rec["gargling_id"]]["first_name"]
            ppl.append(f"{name} {data['emoji']} ({fdate(rec['taken_at'])})")
        res += " & ".join(ppl)
        return res

    result = []
    for data in records:
        if data["collective"]:
            res = format_col(data)
        else:
            res = format_ind(data)
        result.append(res)
    return "\n".join(result)


def all_at_date(conn: connection, date: pendulum.Date = None) -> str:
    ongoing_journey = common.queries.journey.get_ongoing_journey(conn)
    journey_id = ongoing_journey["id"]
    all_records = get_all_at_date(conn, journey_id, date)
    gargling_ids = set()
    for record in all_records:
        for rec in record["records"]:
            gargling_id = rec.get("gargling_id")
            if gargling_id:
                gargling_ids.add(gargling_id)
    gargling_info = common.get_colors_names(conn, ids=list(gargling_ids))
    formatted = format_all(gargling_info, all_records)
    return formatted
