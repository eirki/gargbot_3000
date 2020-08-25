#! /usr/bin/env python3
# coding: utf-8
import pendulum
from psycopg2.extensions import connection

from gargbot_3000.health import queries
from gargbot_3000.health.polar import PolarUser


def polar_user(conn):
    tokens = queries.tokens(conn)
    tokens = [dict(token) for token in tokens]
    users = [PolarUser(**token) for token in tokens if token.pop("service") == "polar"]
    assert len(users) == 1
    return users[0]


class FakePolarTrans:
    def __init__(self, activities):
        self.activities = {i: act for i, act in enumerate(activities)}

    def list_activities(self):
        return {"activity-log": self.activities.keys()}

    def get_activity_summary(self, activity):
        return self.activities[activity]

    def commit(self):
        pass


def test_polar_steps(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [{"created": "2020-01-02T20:11:33.000Z", "active-steps": 1500}]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1500


def test_polar_steps_cached(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    user = polar_user(conn)
    to_cache = [
        {
            "created_at": "2020-01-02T12:11:33.000Z",
            "n_steps": 1500,
            "gargling_id": user.gargling_id,
        }
    ]
    queries.upsert_steps(conn, to_cache)
    tran = FakePolarTrans(
        [{"created": "2020-01-02T20:11:33.000Z", "active-steps": 1000}]
    )
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1000


def test_polar_steps_multiple_dates(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {"created": "2020-01-01T20:11:33.000Z", "active-steps": 1500},
            {"created": "2020-01-02T20:11:33.000Z", "active-steps": 1501},
            {"created": "2020-01-03T20:11:33.000Z", "active-steps": 1502},
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1501


def test_polar_steps_multiple_same_date(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {"created": "2020-01-02T16:11:33.000Z", "active-steps": 1499},
            {"created": "2020-01-02T20:11:33.000Z", "active-steps": 1501},
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    steps = user.steps(test_date, conn)
    assert steps == 1501


def test_polar_steps_future_cached(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    tran = FakePolarTrans(
        [
            {"created": "2020-01-02T20:11:33.000Z", "active-steps": 1501},
            {"created": "2020-01-03T20:11:33.000Z", "active-steps": 1502},
        ]
    )
    user = polar_user(conn)
    user._get_transaction = lambda: tran  # type: ignore
    user.steps(test_date, conn)
    future = test_date.add(days=1)
    cached = queries.cached_step_for_date(conn, date=future, id=user.gargling_id)
    assert cached["n_steps"] == 1502
