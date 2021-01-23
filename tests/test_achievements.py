#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import pendulum
from psycopg2.extensions import connection

from gargbot_3000.journey import achievements, journey
from gargbot_3000.journey.achievements import queries
from tests import test_journey


def test_most_steps_one_day_individual_new_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 11521},
        {"gargling_id": 3, "amount": 6380},
        {"gargling_id": 5, "amount": 111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.most_steps_one_day_individual,
        conn=conn,
        journey_id=journey_id,
        date=date,
        less_than=None,
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders == [6]
    assert value == 17782
    assert prev_holders == {6}
    assert prev_value == 1778


def test_most_steps_one_day_individual_tangering(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 17782},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 11521},
        {"gargling_id": 3, "amount": 6380},
        {"gargling_id": 5, "amount": 111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.most_steps_one_day_individual,
        conn=conn,
        journey_id=journey_id,
        date=date,
        less_than=None,
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders == [6]
    assert value == 17782
    assert prev_holders == {3, 6}
    assert prev_value is None


def test_most_steps_one_day_individual_no_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 1},
        {"gargling_id": 2, "amount": 1},
        {"gargling_id": 3, "amount": 1},
        {"gargling_id": 5, "amount": 1},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.most_steps_one_day_individual,
        conn=conn,
        journey_id=journey_id,
        date=date,
        less_than=None,
    )
    assert achv is None


def test_most_steps_one_day_individual_some_data(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)
    achv = achievements.extract(
        query=queries.most_steps_one_day_individual,
        conn=conn,
        journey_id=journey_id,
        date=date,
        less_than=None,
    )
    assert achv is None


def test_most_steps_one_day_individual_no_data(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    achv = achievements.extract(
        query=queries.most_steps_one_day_individual,
        conn=conn,
        journey_id=journey_id,
        date=date,
        less_than=None,
    )
    assert achv is None


def test_most_steps_one_day_collective_new_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 11521},
        {"gargling_id": 3, "amount": 6380},
        {"gargling_id": 5, "amount": 111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.most_steps_one_day_collective,
        conn=conn,
        journey_id=journey_id,
        date=date,
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders is None
    assert value == 35794
    assert prev_holders is None
    assert prev_value == 3579


def test_highest_share_new_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 25},
        {"gargling_id": 2, "amount": 25},
        {"gargling_id": 3, "amount": 30},
        {"gargling_id": 5, "amount": 20},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 5},
        {"gargling_id": 2, "amount": 5},
        {"gargling_id": 3, "amount": 5},
        {"gargling_id": 5, "amount": 85},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.highest_share, conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders == [5]
    assert value == 85
    assert prev_holders == {3}
    assert prev_value == 30


def test_biggest_improvement_individual_new_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 11521},
        {"gargling_id": 3, "amount": 6380},
        {"gargling_id": 5, "amount": 111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 7782},
        {"gargling_id": 2, "amount": 1521},
        {"gargling_id": 3, "amount": 380},
        {"gargling_id": 5, "amount": 20111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.biggest_improvement_individual,
        conn=conn,
        journey_id=journey_id,
        date=date,
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders == [5]
    assert value == 20000
    assert prev_holders == {6}
    assert prev_value == 16004


def test_biggest_improvement_collective_new_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1},
        {"gargling_id": 2, "amount": 1},
        {"gargling_id": 3, "amount": 1},
        {"gargling_id": 5, "amount": 1},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 10},
        {"gargling_id": 2, "amount": 10},
        {"gargling_id": 3, "amount": 10},
        {"gargling_id": 5, "amount": 10},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 100},
        {"gargling_id": 2, "amount": 100},
        {"gargling_id": 3, "amount": 100},
        {"gargling_id": 5, "amount": 100},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.biggest_improvement_collective,
        conn=conn,
        journey_id=journey_id,
        date=date,
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders is None
    assert value == 360
    assert prev_holders is None
    assert prev_value == 36


def test_longest_streak_new_record(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
    steps_data = [
        {"gargling_id": 6, "amount": 1},
        {"gargling_id": 2, "amount": 2000},
        {"gargling_id": 3, "amount": 2000},
        {"gargling_id": 5, "amount": 1},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 2000},
        {"gargling_id": 2, "amount": 2000},
        {"gargling_id": 3, "amount": 1},
        {"gargling_id": 5, "amount": 1},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 2000},
        {"gargling_id": 2, "amount": 1},
        {"gargling_id": 3, "amount": 1},
        {"gargling_id": 5, "amount": 2000},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 1},
        {"gargling_id": 2, "amount": 1},
        {"gargling_id": 3, "amount": 1},
        {"gargling_id": 5, "amount": 2000},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)
    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 1},
        {"gargling_id": 2, "amount": 1},
        {"gargling_id": 3, "amount": 1},
        {"gargling_id": 5, "amount": 2000},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.extract(
        query=queries.longest_streak, conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    holders, value, prev_holders, prev_value = achv
    assert holders == [5]
    assert value == 3
    assert prev_holders == {2, 5, 6}
    assert prev_value == 2


def test_format_new_individual():
    gargling_info = {
        6: {"first_name": "gargling 6"},
        2: {"first_name": "gargling 2"},
        3: {"first_name": "gargling 3"},
        5: {"first_name": "gargling 5"},
    }

    desc = "Flest skritt gått av en gargling på én dag"
    unit = "skritt"
    holders = [6]
    value = 17782
    prev_holders = {6}
    prev_value = 1778
    formatted = achievements.format_new(
        desc, unit, holders, value, prev_holders, prev_value, gargling_info
    )
    assert formatted == (
        "gargling 6 :first_place_medal: har satt ny rekord: Flest skritt gått av en gargling på én dag, med 17782 skritt! "
        "Forrige record holder var gargling 6, med 1778 skritt. Huzzah! :sonic:"
    )


def test_format_new_individual_multiple():
    gargling_info = {
        6: {"first_name": "gargling 6"},
        2: {"first_name": "gargling 2"},
        3: {"first_name": "gargling 3"},
        5: {"first_name": "gargling 5"},
    }

    desc = "Flest skritt gått av en gargling på én dag"
    unit = "skritt"
    holders = [6, 2]
    value = 17782
    prev_holders = {3}
    prev_value = 1778
    formatted = achievements.format_new(
        desc, unit, holders, value, prev_holders, prev_value, gargling_info
    )
    assert formatted == (
        "gargling 6 :first_place_medal: og gargling 2 :first_place_medal: har satt ny rekord: "
        "Flest skritt gått av en gargling på én dag, med 17782 skritt! "
        "Forrige record holder var gargling 3, med 1778 skritt. Huzzah! :sonic:"
    )


def test_format_new_individual_tangerin():
    gargling_info = {
        6: {"first_name": "gargling 6"},
        2: {"first_name": "gargling 2"},
        3: {"first_name": "gargling 3"},
        5: {"first_name": "gargling 5"},
    }
    desc = "Flest skritt gått av en gargling på én dag"
    unit = "skritt"
    holders = [6]
    value = 17782
    prev_holders = {3, 6}
    prev_value = None
    formatted = achievements.format_new(
        desc, unit, holders, value, prev_holders, prev_value, gargling_info
    )
    assert formatted == (
        "gargling 6 :sports_medal: har tangert rekord: Flest skritt gått av en gargling på én dag (17782 skritt)! "
        "Forrige record holders var gargling 3 og gargling 6. Huzzah! :sonic:"
    )


def test_format_new_collective_new_record():
    gargling_info = {
        6: {"first_name": "gargling 6"},
        2: {"first_name": "gargling 2"},
        3: {"first_name": "gargling 3"},
        5: {"first_name": "gargling 5"},
    }
    desc = "Flest skritt gått av hele gargen på én dag"
    unit = "skritt"
    holders = None
    value = 35794
    prev_holders = None
    prev_value = 3579
    formatted = achievements.format_new(
        desc, unit, holders, value, prev_holders, prev_value, gargling_info
    )
    assert formatted == (
        "Vi :first_place_medal: har satt ny rekord: Flest skritt gått av hele gargen på én dag, med 35794 skritt! "
        "Forrige rekord var 3579 skritt. Huzzah! :sonic:"
    )


def test_all(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 11521},
        {"gargling_id": 3, "amount": 6380},
        {"gargling_id": 5, "amount": 111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    date = date.add(days=1)
    steps_data = [
        {"gargling_id": 6, "amount": 7782},
        {"gargling_id": 2, "amount": 1521},
        {"gargling_id": 3, "amount": 380},
        {"gargling_id": 5, "amount": 20111},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)

    achv = achievements.get_all_at_date(conn, journey_id=journey_id)

    assert achv is not None
    (
        most_d,
        second_most_d,
        third_most_d,
        most_collective_d,
        highest_share_d,
        improvement_d,
        improvement_collective_d,
        streak_d,
    ) = achv
    most_l = most_d["records"]
    assert len(most_l) == 1
    most = most_l[0]
    assert dict(most) == {
        "amount": 20111,
        "gargling_id": 5,
        "taken_at": pendulum.Date(2000, 1, 3),
    }
    second_most_l = second_most_d["records"]
    assert len(second_most_l) == 1
    second_most = second_most_l[0]
    assert dict(second_most) == {
        "amount": 17782,
        "gargling_id": 6,
        "taken_at": pendulum.Date(2000, 1, 2),
    }
    third_most_l = third_most_d["records"]
    assert len(third_most_l) == 1
    third_most = third_most_l[0]
    assert dict(third_most) == {
        "amount": 11521,
        "gargling_id": 2,
        "taken_at": pendulum.Date(2000, 1, 2),
    }
    most_collective_l = most_collective_d["records"]
    assert len(most_collective_l) == 1
    most_collective = most_collective_l[0]
    assert dict(most_collective) == {
        "amount": 35794,
        "taken_at": pendulum.Date(2000, 1, 2),
    }
    highest_share_l = highest_share_d["records"]
    assert len(highest_share_l) == 1
    highest_share = highest_share_l[0]
    assert dict(highest_share) == {
        "amount": 68,
        "gargling_id": 5,
        "taken_at": pendulum.Date(2000, 1, 3),
    }
    improvement_l = improvement_d["records"]
    assert len(improvement_l) == 1
    improvement = improvement_l[0]
    assert dict(improvement) == {
        "amount": 20000,
        "gargling_id": 5,
        "taken_at": pendulum.Date(2000, 1, 3),
    }
    improvement_collective_l = improvement_collective_d["records"]
    assert len(improvement_collective_l) == 1
    improvement_collective = improvement_collective_l[0]
    assert dict(improvement_collective) == {
        "amount": 32215,
        "taken_at": pendulum.Date(2000, 1, 2),
    }
    streak_l = streak_d["records"]
    assert len(streak_l) == 1
    streak = streak_l[0]
    assert dict(streak) == {
        "amount": 2,
        "gargling_id": 6,
        "taken_at": pendulum.Date(2000, 1, 2),
    }


def test_format_all():
    records = [
        {
            "desc": "Flest skritt gått av en gargling på én dag",
            "records": [
                {
                    "amount": 20111,
                    "gargling_id": 5,
                    "taken_at": pendulum.Date(2000, 1, 3),
                }
            ],
            "collective": False,
            "unit": "skritt",
            "emoji": ":first_place_medal:",
        },
        {
            "desc": "Nest flest skritt gått av en gargling på én dag",
            "records": [
                {
                    "amount": 17782,
                    "gargling_id": 6,
                    "taken_at": pendulum.Date(2000, 1, 2),
                }
            ],
            "collective": False,
            "unit": "skritt",
            "emoji": ":second_place_medal:",
        },
        {
            "desc": "Tredje flest skritt gått av en gargling på én dag",
            "records": [
                {
                    "amount": 11521,
                    "gargling_id": 2,
                    "taken_at": pendulum.Date(2000, 1, 2),
                }
            ],
            "collective": False,
            "unit": "skritt",
            "emoji": ":third_place_medal:",
        },
        {
            "desc": "Flest skritt gått av hele gargen på én dag",
            "records": [{"amount": 35794, "taken_at": pendulum.Date(2000, 1, 2)}],
            "collective": True,
            "emoji": ":trophy:",
            "unit": "skritt",
        },
        {
            "desc": "Størst andel av dagens skritt",
            "records": [
                {"amount": 68, "gargling_id": 5, "taken_at": pendulum.Date(2000, 1, 3)}
            ],
            "collective": False,
            "unit": "%",
            "emoji": ":sports_medal:",
        },
        {
            "desc": "Størst improvement fra en dag til neste for en gargling",
            "records": [
                {
                    "amount": 20000,
                    "gargling_id": 5,
                    "taken_at": pendulum.Date(2000, 1, 3),
                }
            ],
            "collective": False,
            "unit": "skritt",
            "emoji": ":sports_medal:",
        },
        {
            "desc": "Størst improvement fra en dag til neste for hele gargen",
            "records": [{"amount": 32215, "taken_at": pendulum.Date(2000, 1, 2)}],
            "collective": True,
            "emoji": ":trophy:",
            "unit": "skritt",
        },
        {
            "desc": "Lengste streak med førsteplasser",
            "records": [
                {"amount": 2, "gargling_id": 6, "taken_at": pendulum.Date(2000, 1, 2)}
            ],
            "collective": False,
            "unit": "dager",
            "emoji": ":sports_medal:",
        },
    ]
    gargling_info = {
        6: {"first_name": "gargling 6"},
        2: {"first_name": "gargling 2"},
        3: {"first_name": "gargling 3"},
        5: {"first_name": "gargling 5"},
    }

    formatted = achievements.format_all(gargling_info, records)
    assert formatted == (
        "Flest skritt gått av en gargling på én dag: 20111 skritt - gargling 5 :first_place_medal: (3.1.2000)\n"
        "Nest flest skritt gått av en gargling på én dag: 17782 skritt - gargling 6 :second_place_medal: (2.1.2000)\n"
        "Tredje flest skritt gått av en gargling på én dag: 11521 skritt - gargling 2 :third_place_medal: (2.1.2000)\n"
        "Flest skritt gått av hele gargen på én dag: 35794 skritt :trophy: - 2.1.2000\n"
        "Størst andel av dagens skritt: 68 % - gargling 5 :sports_medal: (3.1.2000)\n"
        "Størst improvement fra en dag til neste for en gargling: 20000 skritt - gargling 5 :sports_medal: (3.1.2000)\n"
        "Størst improvement fra en dag til neste for hele gargen: 32215 skritt :trophy: - 2.1.2000\n"
        "Lengste streak med førsteplasser: 2 dager - gargling 6 :sports_medal: (2.1.2000)"
    )


def test_format_all2():
    records = [
        {
            "desc": "Flest skritt gått av en gargling på én dag",
            "unit": "skritt",
            "records": [
                {
                    "amount": 20111,
                    "gargling_id": 5,
                    "taken_at": pendulum.Date(2000, 1, 3),
                },
                {
                    "amount": 20111,
                    "gargling_id": 2,
                    "taken_at": pendulum.Date(2000, 1, 1),
                },
            ],
            "collective": False,
            "emoji": ":first_place_medal:",
        },
        {
            "desc": "Flest skritt gått av hele gargen på én dag",
            "unit": "skritt",
            "records": [
                {"amount": 35794, "taken_at": pendulum.Date(2000, 1, 2)},
                {"amount": 35794, "taken_at": pendulum.Date(2000, 1, 3)},
            ],
            "collective": True,
            "emoji": ":trophy:",
        },
    ]
    gargling_info = {
        6: {"first_name": "gargling 6"},
        2: {"first_name": "gargling 2"},
        3: {"first_name": "gargling 3"},
        5: {"first_name": "gargling 5"},
    }
    formatted = achievements.format_all(gargling_info, records)
    assert formatted == (
        "Flest skritt gått av en gargling på én dag: 20111 skritt - gargling 5 :first_place_medal: "
        "(3.1.2000) & gargling 2 :first_place_medal: (1.1.2000)\n"
        "Flest skritt gått av hele gargen på én dag: 35794 skritt :trophy: - 2.1.2000 & 3.1.2000"
    )


def test_all_at_date(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
    steps_data = [
        {"gargling_id": 6, "amount": 1778},
        {"gargling_id": 2, "amount": 1152},
        {"gargling_id": 3, "amount": 638},
        {"gargling_id": 5, "amount": 11},
    ]
    journey.store_steps(conn, steps_data, journey_id, date)
    achv = achievements.all_at_date(conn=conn, date=date)
    assert achv == (
        "Flest skritt gått av en gargling på én dag: 1778 skritt - name6 :first_place_medal: (1.1.2000)\n"
        "Nest flest skritt gått av en gargling på én dag: 1152 skritt - name2 :second_place_medal: (1.1.2000)\n"
        "Tredje flest skritt gått av en gargling på én dag: 638 skritt - name3 :third_place_medal: (1.1.2000)\n"
        "Flest skritt gått av hele gargen på én dag: 3579 skritt :trophy: - 1.1.2000\n"
        "Størst andel av dagens skritt: 50 % - name6 :sports_medal: (1.1.2000)\n"
        "Lengste streak med førsteplasser: 1 dager - name6 :sports_medal: (1.1.2000)"
    )
