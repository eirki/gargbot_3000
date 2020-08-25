#! /usr/bin/env python3
# coding: utf-8

import typing as t

import pendulum
from psycopg2.extensions import connection

from gargbot_3000.health import queries
from gargbot_3000.health.fitbit_ import FitbitUser


def fitbit_users(conn):
    tokens = queries.tokens(conn)
    tokens = [dict(token) for token in tokens]
    users = [
        FitbitUser(**token) for token in tokens if token.pop("service") == "fitbit"
    ]
    assert len(users) == 2
    return users


def test_fitbit_steps(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13475"},
            {"dateTime": "2019-12-29", "value": "1"},
        ]
    }
    user2_return_value = {
        "activities-steps": [
            {"dateTime": "2020-01-01", "value": "13474"},
            {"dateTime": "2020-01-02", "value": "86"},
        ]
    }
    user1._steps_api_call = lambda date: user1_return_value
    user2._steps_api_call = lambda date: user2_return_value
    test_date = pendulum.Date(2020, 1, 2)
    steps = [user.steps(test_date) for user in users]
    assert steps == [13475, 13474]


def test_fitbit_steps_no_data(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_return_value: t.Dict[str, list] = {"activities-steps": []}
    user2_return_value: t.Dict[str, list] = {"activities-steps": []}
    user1._steps_api_call = lambda date: user1_return_value
    user2._steps_api_call = lambda date: user2_return_value
    test_date = pendulum.Date(2020, 1, 2)
    steps = [user.steps(test_date) for user in users]
    assert steps == [None, None]


def test_fitbit_body(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_weight_return_value = {
        "weight": [{"date": "2019-01-02", "time": "10:11:12", "weight": 50}]
    }
    user1_bodyfat_return_value = {
        "fat": [{"date": "2019-01-02", "time": "10:11:12", "fat": 5}]
    }
    user1._weight_api_call = lambda date: user1_weight_return_value
    user1._bodyfat_api_call = lambda date: user1_bodyfat_return_value
    user2_weight_return_value = {
        "weight": [
            {"date": "2020-01-01", "time": "10:11:12", "weight": 75},
            {"date": "2020-01-02", "time": "10:11:12", "weight": 100},
        ]
    }
    user2_bodyfat_return_value = {
        "fat": [
            {"date": "2020-01-01", "time": "10:11:12", "fat": 7},
            {"date": "2020-01-02", "time": "10:11:12", "fat": 10},
        ]
    }
    user2._weight_api_call = lambda date: user2_weight_return_value
    user2._bodyfat_api_call = lambda date: user2_bodyfat_return_value

    test_date = pendulum.Date(2020, 1, 2)
    data = [user.body(test_date) for user in users]
    expected = [
        {"elapsed": 365, "weight": None, "fat": None},
        {"elapsed": None, "weight": 100, "fat": 10},
    ]
    assert data == expected


def test_fitbit_body_no_data(conn: connection):
    users = fitbit_users(conn)
    user1, user2 = users
    user1_weight_return_value: t.Dict[str, list] = {"weight": []}
    user1_bodyfat_return_value: t.Dict[str, list] = {"fat": []}
    user1._weight_api_call = lambda date: user1_weight_return_value
    user1._bodyfat_api_call = lambda date: user1_bodyfat_return_value
    user2_weight_return_value: t.Dict[str, list] = {"weight": []}
    user2_bodyfat_return_value: t.Dict[str, list] = {"fat": []}
    user2._weight_api_call = lambda date: user2_weight_return_value
    user2._bodyfat_api_call = lambda date: user2_bodyfat_return_value
    expected = [
        {"elapsed": None, "fat": None, "weight": None},
        {"elapsed": None, "fat": None, "weight": None},
    ]
    test_date = pendulum.Date(2020, 1, 2)
    data = [user.body(test_date) for user in users]
    assert data == expected
