#! /usr/bin/env python3
# coding: utf-8

import pendulum
from psycopg2.extensions import connection

from gargbot_3000.journey import achievements, journey
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

    achv = achievements.most_steps_one_day_individual(
        conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Flest skritt gått av en gargling på én dag"
    assert unit == "skritt"
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

    achv = achievements.most_steps_one_day_individual(
        conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Flest skritt gått av en gargling på én dag"
    assert unit == "skritt"
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

    achv = achievements.most_steps_one_day_individual(
        conn=conn, journey_id=journey_id, date=date
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
    achv = achievements.most_steps_one_day_individual(
        conn=conn, journey_id=journey_id, date=date
    )
    assert achv is None


def test_most_steps_one_day_individual_no_data(conn: connection):
    date = pendulum.Date(2000, 1, 1)
    journey_id = test_journey.insert_journey_data(conn)
    achv = achievements.most_steps_one_day_individual(
        conn=conn, journey_id=journey_id, date=date
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

    achv = achievements.most_steps_one_day_collective(
        conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Flest skritt gått av hele gargen på én dag"
    assert unit == "skritt"
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

    achv = achievements.highest_share(conn=conn, journey_id=journey_id, date=date)
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Størst andel av dagens skritt"
    assert unit == "%"
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

    achv = achievements.biggest_improvement_individual(
        conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Størst improvement fra en dag til neste for en gargling"
    assert unit == "skritt"
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

    achv = achievements.biggest_improvement_collective(
        conn=conn, journey_id=journey_id, date=date
    )
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Størst improvement fra en dag til neste for hele gargen"
    assert unit == "skritt"
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

    achv = achievements.longest_streak(conn=conn, journey_id=journey_id, date=date)
    assert achv is not None
    desc, unit, holders, value, prev_holders, prev_value = achv
    assert desc == "Lengste streak med førsteplasser"
    assert unit == "dager"
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
