#! /usr/bin/env python3.6
# coding: utf-8
from contextlib import contextmanager
from operator import itemgetter
import random
import typing as t
from unittest.mock import DEFAULT, Mock, patch

from PIL import Image
from flask.testing import FlaskClient
import pendulum
import psycopg2
from psycopg2.extensions import connection
import pytest

from gargbot_3000 import journey

xml = """<?xml version="1.0" encoding="UTF-8" standalone="no" ?><gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" creator="Graphhopper version f738fdfc4371477dfe39f433b7802f9f6348627a" version="1.1" xmlns:gh="https://graphhopper.com/public/schema/gpx/1.1">
<trk><name>GraphHopper Track</name><trkseg>
<trkpt lat="47.586392" lon="40.688998"></trkpt>
<trkpt lat="47.586482" lon="40.690648"></trkpt>
<trkpt lat="47.586346" lon="40.692903"></trkpt>
<trkpt lat="47.586119" lon="40.694385"></trkpt>
<trkpt lat="47.585707" lon="40.695735"></trkpt>
<trkpt lat="47.58235" lon="40.70435"></trkpt>
<trkpt lat="47.581214" lon="40.707144"></trkpt>
<trkpt lat="47.580374" lon="40.708726"></trkpt>
<trkpt lat="47.579466" lon="40.710005"></trkpt>
<trkpt lat="47.577354" lon="40.71216"></trkpt>
<trkpt lat="47.54918" lon="40.750911"></trkpt>
<trkpt lat="47.523033" lon="40.764962"></trkpt>
<trkpt lat="47.427366" lon="41.011354"></trkpt>
<trkpt lat="47.327962" lon="41.309018"></trkpt>
</trkseg>
</trk>
</gpx>"""

gps_data = [
    {"lat": 47.586392, "lon": 40.688998, "cum_dist": 0.000000},
    {"lat": 47.586482, "lon": 40.690648, "cum_dist": 124.290397},
    {"lat": 47.586346, "lon": 40.692903, "cum_dist": 294.277151},
    {"lat": 47.586119, "lon": 40.694385, "cum_dist": 408.383249},
    {"lat": 47.585707, "lon": 40.695735, "cum_dist": 519.639149},
    {"lat": 47.582350, "lon": 40.704350, "cum_dist": 1266.708526},
    {"lat": 47.581214, "lon": 40.707144, "cum_dist": 1511.674758},
    {"lat": 47.580374, "lon": 40.708726, "cum_dist": 1662.856365},
    {"lat": 47.579466, "lon": 40.710005, "cum_dist": 1802.287666},
    {"lat": 47.577354, "lon": 40.712160, "cum_dist": 2087.707336},
    {"lat": 47.549180, "lon": 40.750911, "cum_dist": 6367.173839},
    {"lat": 47.523033, "lon": 40.764962, "cum_dist": 9463.573534},
    {"lat": 47.427366, "lon": 41.011354, "cum_dist": 30843.651920},
    {"lat": 47.327962, "lon": 41.309018, "cum_dist": 55862.151884},
]


class MockHealth:
    steps = {
        0: (11521, 6380, 111, 17782),
        1: (14035, 2507, 6236, 911),
        2: (5166, 9151, 4212, 14041),
        3: (11315, 5972, 8992, 10318),
    }

    def __init__(self):
        self.called = 0

    def activity(self, conn, date):
        steps = self.steps[self.called]
        self.called += 1
        steps_data = [
            {"first_name": name, "amount": step}
            for name, step in zip(["name2", "name3", "name5", "name6"], steps)
        ]
        weight_reports = ["name2 veier 60 kg"]
        return steps_data, weight_reports


def insert_journey_data(conn) -> int:
    journey_id = journey.define_journey(
        conn, origin="Origin", destination="Destination"
    )
    data_in: t.List[dict] = [{"journey_id": journey_id, **d} for d in gps_data]
    journey.queries.add_waypoints(conn, data_in)
    return journey_id


def example_update_data() -> dict:
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    expected_steps_data = [
        {"first_name": "name6", "amount": 17782},
        {"first_name": "name2", "amount": 11521},
        {"first_name": "name3", "amount": 6380},
        {"first_name": "name5", "amount": 111},
    ]
    colors = [
        ("#42d4f4", "cyan"),
        ("#3cb44b", "green"),
        ("#f58231", "orange"),
        ("#911eb4", "purple"),
    ]
    for d, (c_hex, c_name) in zip(expected_steps_data, colors):
        d["taken_at"] = date
        d["journey_id"] = 1
        d["color_hex"] = c_hex
        d["color_name"] = c_name
    return {
        "date": date,
        "steps_data": expected_steps_data,
        "dist_today": 26845.5,
        "dist_total": 26845.5,
        "dist_remaining": 29016.651884,
        "address": "Address",
        "poi": "Poi",
        "img_url": "www.image",
        "map_url": "www.mapurl",
        "traversal_map_url": "www.tmap",
        "weight_reports": ["name2 veier 60 kg"],
        "finished": False,
    }


@contextmanager
def api_mocker():
    with patch.multiple(
        "gargbot_3000.journey",
        address_for_location=DEFAULT,
        image_for_location=DEFAULT,
        map_url_for_location=DEFAULT,
        poi_for_location=DEFAULT,
        render_map=DEFAULT,
        upload_images=DEFAULT,
    ) as mocks:
        mocks["address_for_location"].return_value = "Address"
        mocks["image_for_location"].return_value = b"image"
        mocks["map_url_for_location"].return_value = "www.mapurl"
        mocks["poi_for_location"].return_value = "Poi"
        mocks["render_map"].return_value = Image.new("RGB", (500, 300))
        mocks["upload_images"].return_value = "www.image", "www.tmap"
        yield


@patch("gargbot_3000.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_list_journeys(
    mock_jwt_required, mock_jwt_identity, client: FlaskClient, conn: connection
):
    journey_id = insert_journey_data(conn)
    date1 = pendulum.datetime(2013, 3, 31, tz="UTC")
    location1 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 300,
        "latest_waypoint": 2,
        "address": "address1",
        "img_url": "image1",
        "map_url": "map_url1",
        "traversal_map_url": "tmap_url1",
        "poi": "poi1",
    }

    date2 = pendulum.datetime(2013, 4, 10, tz="UTC")
    location2 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 301,
        "latest_waypoint": 3,
        "address": "address2",
        "img_url": "image2",
        "map_url": "map_url2",
        "traversal_map_url": "tmap_url2",
        "poi": "poi2",
    }
    journey.queries.add_location(conn, journey_id=journey_id, date=date1, **location1)
    journey.queries.add_location(conn, journey_id=journey_id, date=date2, **location2)
    response = client.get("/list_journeys")
    assert len(response.json["journeys"]) == 1


def test_detail_journey(client: FlaskClient, conn: connection):
    journey_id = insert_journey_data(conn)
    health = MockHealth()
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    with api_mocker():
        journey.perform_daily_update(conn, health.activity, journey_id, date)
        response = client.get(f"/detail_journey/{journey_id}")
    waypoints = response.json.pop("waypoints")
    length = len(waypoints) - 1
    assert waypoints[:length] == gps_data[:length]
    loc = journey.most_recent_location(conn, journey_id)
    assert loc is not None
    assert waypoints[length]["cum_dist"] == loc["distance"]
    assert waypoints[length]["lat"] == loc["lat"]
    assert waypoints[length]["lon"] == loc["lon"]
    expected = {
        "destination": "Destination",
        "distance": 55862.151884,
        "finished_at": None,
        "id": 1,
        "ongoing": True,
        "origin": "Origin",
        "started_at": "Sun, 31 Mar 2013 00:00:00 GMT",
    }
    assert response.json == expected


def test_define_journey(conn):
    journey_id = journey.define_journey(conn, "Origin", "Destination")
    j = journey.queries.get_journey(conn, journey_id=journey_id)
    j["origin"] == "origin"
    j["destination"] == "destination"


def test_parse_xml(conn):
    journey_id = journey.define_journey(conn, "Origin", "Destination")
    journey.parse_gpx(conn=conn, journey_id=journey_id, xml_data=xml)
    data = journey.queries.waypoints_for_journey(conn, journey_id=journey_id)
    assert len(data) == 14


def test_get_location(conn: connection):
    journey_id = insert_journey_data(conn)
    lat, lon, latest_waypoint, finished = journey.get_location(
        conn, journey_id, distance=300
    )
    assert lat == pytest.approx(47.58633461507472)
    assert lon == pytest.approx(40.69297732817553)
    assert latest_waypoint == 3
    assert finished is False


def test_store_get_most_recent_location(conn):
    journey_id = insert_journey_data(conn)
    date1 = pendulum.datetime(2013, 3, 31, tz="UTC")
    location1 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 300,
        "latest_waypoint": 2,
        "address": "address1",
        "img_url": "image1",
        "map_url": "map_url1",
        "traversal_map_url": "tmap_url1",
        "poi": "poi1",
    }

    date2 = pendulum.datetime(2013, 4, 10, tz="UTC")
    location2 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 301,
        "latest_waypoint": 3,
        "address": "address2",
        "img_url": "image2",
        "map_url": "map_url2",
        "traversal_map_url": "tmap_url2",
        "poi": "poi2",
    }

    journey.queries.add_location(conn, journey_id=journey_id, date=date1, **location1)
    journey.queries.add_location(conn, journey_id=journey_id, date=date2, **location2)
    j = journey.most_recent_location(conn, journey_id)
    location2["lat"] = pytest.approx(location2["lat"])
    location2["lon"] = pytest.approx(location2["lon"])
    location2["journey_id"] = journey_id
    location2["date"] = date2
    assert j == location2


def test_start_journey(conn):
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    ongoing = journey.queries.get_ongoing_journey(conn)
    assert dict(ongoing) == {
        "id": journey_id,
        "destination": "Destination",
        "finished_at": None,
        "ongoing": True,
        "origin": "Origin",
        "started_at": date,
    }


def test_start_two_journeys_fails(conn):
    journey_id1 = insert_journey_data(conn)
    journey_id2 = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id1, date)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        journey.start_journey(conn, journey_id2, date)


def test_store_steps(conn: connection):
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    mock_health = MockHealth()
    data_in, _ = mock_health.activity(conn=None, date=None)
    journey.store_steps(conn, data_in, journey_id, date)
    data_out = journey.queries.get_steps(conn, journey_id=journey_id)
    data_out = [dict(d) for d in data_out]
    data_in.sort(key=itemgetter("first_name"))
    data_out.sort(key=itemgetter("first_name"))
    assert len(data_in) == len(data_out)
    for d_in, d_out in zip(data_in, data_out):
        d_out.pop("gargling_id")
        assert d_in == d_out


def test_store_steps_twice_fails(conn: connection):
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    mock_health = MockHealth()
    steps_data, _ = mock_health.activity(conn=None, date=None)
    journey.store_steps(conn, steps_data, journey_id, date)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        journey.store_steps(conn, steps_data, journey_id, date)


def test_daily_update(conn: connection):
    health = MockHealth()
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    with api_mocker():
        data = journey.perform_daily_update(conn, health.activity, journey_id, date)
    assert data is not None
    expected = example_update_data()
    assert data == expected


def test_format_response():
    data = example_update_data()
    data["destination"] = "Destinasjon"

    formatted = journey.format_response(**data)
    expected = {
        "text": "*Ekspedisjonsrapport for 31.3.2013*: Vi gikk *26.8 km*!",
        "blocks": [
            {
                "text": {
                    "text": "*Ekspedisjonsrapport for 31.3.2013*:",
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {
                "text": {
                    "text": "Vi gikk *26.8 km*! Nå har vi gått 26.8 km "
                    "totalt på vår journey til Destinasjon - vi har 29 km igjen til "
                    "vi er framme.",
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {
                "text": {
                    "text": (
                        "Steps taken:\n"
                        "\t:dot-cyan: name6: *17782* (13.3 km) :star:\n"
                        "\t:dot-green: name2: 11521 (8.6 km)\n"
                        "\t:dot-orange: name3: 6380 (4.8 km)\n"
                        "\t:dot-purple: name5: _111_ (83.2 m)"
                    ),
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {"alt_text": "Breakdown!", "image_url": "www.tmap", "type": "image"},
            {
                "text": {
                    "text": "Vi har nå kommet til Address. Kveldens "
                    "underholdning er Poi.",
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {"alt_text": "Address", "image_url": "www.image", "type": "image"},
            {
                "text": {
                    "text": "<www.mapurl|Se deg litt rundt da vel!>",
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {"type": "divider"},
            {
                "text": {"text": "Also: name2 veier 60 kg", "type": "mrkdwn"},
                "type": "section",
            },
        ],
    }
    assert len(formatted["blocks"]) == len(expected["blocks"])
    for f_block, e_block in zip(formatted["blocks"], expected["blocks"]):
        assert f_block == e_block
    assert formatted["text"] == expected["text"]


def test_format_response_no_address():
    data = example_update_data()
    data["destination"] = "Destinasjon"

    data["address"] = None
    response = journey.format_response(**data)
    address_block = response["blocks"][4]
    expected_address = {
        "text": {"text": "Kveldens underholdning er Poi.", "type": "mrkdwn"},
        "type": "section",
    }
    img_block = response["blocks"][5]
    expected_img = {"alt_text": "Check it!", "image_url": "www.image", "type": "image"}
    assert address_block == expected_address
    assert img_block == expected_img


def test_format_response_nopoi():
    data = example_update_data()
    data["destination"] = "Destinasjon"

    data["poi"] = None
    response = journey.format_response(**data)
    address_block = response["blocks"][4]
    expected = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "Vi har nå kommet til Address. "},
    }
    assert address_block == expected


def test_format_response_no_img_url():
    data = example_update_data()
    data["destination"] = "Destinasjon"

    data["img_url"] = None
    response = journey.format_response(**data)
    assert len(response["blocks"]) == 8


def test_format_response_no_all():
    data = example_update_data()
    data["destination"] = "Destinasjon"

    data["address"] = None
    data["poi"] = None
    data["img_url"] = None
    data["traversal_map_url"] = None
    response = journey.format_response(**data)
    assert len(response["blocks"]) == 6


def test_days_to_update_unstarted(conn):
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    next_date = date.add(days=1)
    itr = journey.days_to_update(conn, journey_id, next_date)
    days = list(itr)
    assert days == [date]


def test_days_to_update_unstarted_two_days(conn):
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    next_date = date.add(days=2)
    itr = journey.days_to_update(conn, journey_id, next_date)
    days = list(itr)
    assert days == [date, date.add(days=1)]


def test_days_to_update(conn: connection):
    health = MockHealth()
    journey_id = insert_journey_data(conn)
    start_date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, start_date)
    with api_mocker():
        journey.perform_daily_update(conn, health.activity, journey_id, start_date)

    cur_date = start_date.add(days=2)
    itr = journey.days_to_update(conn, journey_id, cur_date)
    days = list(itr)
    assert days == [cur_date.subtract(days=1)]


def test_journey_finished(conn: connection):
    health = MockHealth()
    journey_id = insert_journey_data(conn)
    start_date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, start_date)
    with api_mocker():
        journey.perform_daily_update(conn, health.activity, journey_id, start_date)
        cur_date = start_date.add(days=4)
        data = []
        for date in journey.days_to_update(conn, journey_id, cur_date):
            datum = journey.perform_daily_update(
                conn, health.activity, journey_id, date
            )
            data.append(datum)
        last_loc = [datum for datum in data if datum is not None][-1]
    assert last_loc["finished"]


@patch("gargbot_3000.journey.health.activity")
def test_journey_main(
    mock_activity, conn: connection,
):

    health = MockHealth()
    mock_activity.return_value = health.activity(conn=None, date=None)
    journey_id = insert_journey_data(conn)
    start_date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, start_date)
    pendulum.set_test_now(start_date.add(days=2))
    with api_mocker():
        dat = journey.main(conn)
    assert len(dat) == 2
    assert dat[0]["blocks"][0]["text"]["text"] == "*Ekspedisjonsrapport for 31.3.2013*:"
    assert dat[1]["blocks"][0]["text"]["text"] == "*Ekspedisjonsrapport for 1.4.2013*:"
