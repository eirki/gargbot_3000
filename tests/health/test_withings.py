#! /usr/bin/env python3
# coding: utf-8
import arrow
import pendulum
from psycopg2.extensions import connection
from withings_api.common import MeasureGetActivityActivity, MeasureGetActivityResponse

from gargbot_3000.health import queries
from gargbot_3000.health.withings import WithingsUser

unused_measures = [
    "timezone",
    "deviceid",
    "brand",
    "is_tracker",
    "distance",
    "elevation",
    "soft",
    "moderate",
    "intense",
    "active",
    "calories",
    "totalcalories",
    "hr_average",
    "hr_min",
    "hr_max",
    "hr_zone_0",
    "hr_zone_1",
    "hr_zone_2",
    "hr_zone_3",
]


def withings_user(conn):
    tokens = queries.tokens(conn)
    tokens = [dict(token) for token in tokens]
    users = [
        WithingsUser(**token) for token in tokens if token.pop("service") == "withings"
    ]
    assert len(users) == 1
    return users[0]


def test_withings_steps(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    none_data = {measure: None for measure in unused_measures}
    n_steps = 6620
    return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(date=test_date, steps=n_steps, **none_data),
        ),
        more=False,
        offset=0,
    )
    user = withings_user(conn)
    user._steps_api_call = lambda date: return_value
    steps = user.steps(test_date)
    assert steps == n_steps


def test_withings_steps_no_data(conn: connection):
    test_date = pendulum.Date(2020, 1, 2)
    none_data = {measure: None for measure in unused_measures}

    return_value = MeasureGetActivityResponse(
        activities=(
            MeasureGetActivityActivity(
                date=arrow.get(test_date.subtract(days=1)), steps=123, **none_data
            ),
        ),
        more=False,
        offset=0,
    )
    user = withings_user(conn)
    user._steps_api_call = lambda date: return_value
    steps = user.steps(test_date)
    assert steps is None
