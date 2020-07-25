#! /usr/bin/env python3.6
# coding: utf-8
import random
from unittest.mock import Mock, patch

import pendulum
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


class MockHealth:
    steps = {
        0: (11521, 6380, 111, 17782),
        1: (14035, 2507, 6236, 911),
        2: (5166, 9151, 4212, 14041),
        3: (11315, 5972, 8992, 10318),
    }

    def __init__(self):
        self.called = 0

    def steps_today(self, date):
        steps = self.steps[self.called]
        self.called += 1
        return [{"gargling_id": i, "amount": step} for i, step in enumerate(steps)]
        # return [
        #     {"gargling_id": 0, "amount": random.randrange(20_000)},
        #     {"gargling_id": 1, "amount": random.randrange(20_000)},
        #     {"gargling_id": 2, "amount": random.randrange(20_000)},
        #     {"gargling_id": 3, "amount": random.randrange(20_000)},
        # ]


def insert_journey_data(conn) -> int:
    journey_id = journey.define_journey(
        conn, origin="Origin", destination="Destination"
    )
    data = [
        (47.586392, 40.688998, 0.000000),
        (47.586482, 40.690648, 124.290397),
        (47.586346, 40.692903, 294.277151),
        (47.586119, 40.694385, 408.383249),
        (47.585707, 40.695735, 519.639149),
        (47.582350, 40.704350, 1266.708526),
        (47.581214, 40.707144, 1511.674758),
        (47.580374, 40.708726, 1662.856365),
        (47.579466, 40.710005, 1802.287666),
        (47.577354, 40.712160, 2087.707336),
        (47.549180, 40.750911, 6367.173839),
        (47.523033, 40.764962, 9463.573534),
        (47.427366, 41.011354, 30843.651920),
        (47.327962, 41.309018, 55862.151884),
    ]
    data_as_dict = [
        {
            "index": i,
            "journey_id": journey_id,
            "lat": lat,
            "lon": lon,
            "cum_dist": cum_dist,
        }
        for i, (lat, lon, cum_dist) in enumerate(data)
    ]
    conn.add_points(points=data_as_dict)
    return journey_id


# @pytest.fixture
# @patch("gargbot_3000.journey.address_for_location")
# @patch("gargbot_3000.journey.image_for_location")
# @patch("gargbot_3000.journey.map_url_for_location")
# @patch("gargbot_3000.journey.poi_for_location")
# def mock_geo_services(
#     mock_poi_func, mock_map_url_func, mock_image_func, mock_address_func
# ):
#     mock_poi_func.return_value = "Poi"
#     mock_map_url_func.return_value = "www.mapurl"
#     mock_image_func.return_value = "www.image"
#     mock_address_func.return_value = "Adress"


def test_define_journey():
    conn = journey.MockSQL()
    journey_id = journey.define_journey(conn, "origin", "destination")
    j = conn.get_journey(journey_id)
    j["origin"] == "origin"
    j["destination"] == "destination"


def test_parse_xml():
    conn = journey.MockSQL()
    journey_id = 1
    journey.parse_gpx(conn=conn, journey_id=journey_id, xml_data=xml)
    data = conn.get_points(journey_id)
    assert len(data) == 10


@patch("gargbot_3000.journey.address_for_location")
@patch("gargbot_3000.journey.image_for_location")
@patch("gargbot_3000.journey.map_url_for_location")
@patch("gargbot_3000.journey.poi_for_location")
# @pytest.mark.usefixtures("mock_geo_services")
def test_get_location(
    mock_poi_func, mock_map_url_func, mock_image_func, mock_address_func
):
    mock_poi_func.return_value = None
    mock_map_url_func.return_value = None
    mock_image_func.return_value = None
    mock_address_func.return_value = None
    conn = journey.MockSQL()
    journey_id = insert_journey_data(conn)
    location = journey.get_location(conn, journey_id, distance=300)
    assert location == {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 300,
        "latest_point": 2,
        "address": None,
        "img_url": None,
        "map_url": None,
        "poi": None,
    }


def test_store_get_most_recent_location():
    conn = journey.MockSQL()
    journey_id = 1
    date1 = pendulum.datetime(2013, 3, 31, tz="UTC")
    location1 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 300,
        "latest_point": 2,
        "next_point": 3,
        "address": "address1",
        "img_url": "image1",
        "map_url": "map_url1",
        "poi": "poi1",
    }

    date2 = pendulum.datetime(2013, 4, 10, tz="UTC")
    location2 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 301,
        "latest_point": 3,
        "next_point": 4,
        "address": "address2",
        "img_url": "image2",
        "map_url": "map_url2",
        "poi": "poi2",
    }

    journey.store_location(conn, journey_id, date1, location1)
    journey.store_location(conn, journey_id, date2, location2)
    j = journey.most_recent_location(conn, journey_id)
    assert j == location2


def test_start_journey():
    conn = journey.MockSQL()
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    ongoing = conn.get_ongoing_journey()
    assert ongoing == {
        "destination": "Destination",
        "finished_at": None,
        "origin": "Origin",
        "started_at": date,
    }


@patch("gargbot_3000.journey.address_for_location")
@patch("gargbot_3000.journey.image_for_location")
@patch("gargbot_3000.journey.map_url_for_location")
@patch("gargbot_3000.journey.poi_for_location")
def test_daily_update(
    mock_poi_func, mock_map_url_func, mock_image_func, mock_address_func
):
    mock_poi_func.return_value = "Poi"
    mock_map_url_func.return_value = "www.mapurl"
    mock_image_func.return_value = "www.image"
    mock_address_func.return_value = "Adress"
    conn = journey.MockSQL()
    client = MockHealth()
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    data = journey.perform_daily_update(conn, client, journey_id, date)
    assert data is not None
    report, img_url, map_url = data
    assert report == (
        "Daily report for 31.3.2013:\n"
        "Steps taken: 3: 17782, 0: 11521, 1: 6380, 2: 111\n"
        "Distance travelled: 26.8 km\n"
        "Distance travelled totalt: 26.8 km\n"
        "Address: Adress\n"
        "Kveldens underholdning: Poi\n"
    )
    assert map_url == "www.mapurl"
    assert img_url == "www.image"


def test_days_to_update_unstarted():
    conn = journey.MockSQL()
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    next_date = date.add(days=1)
    itr = journey.days_to_update(conn, journey_id, next_date)
    days = list(itr)
    assert days == [date]


def test_days_to_update_unstarted_two_days():
    conn = journey.MockSQL()
    journey_id = insert_journey_data(conn)
    date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, date)
    next_date = date.add(days=2)
    itr = journey.days_to_update(conn, journey_id, next_date)
    days = list(itr)
    assert days == [date, date.add(days=1)]


@patch("gargbot_3000.journey.address_for_location")
@patch("gargbot_3000.journey.image_for_location")
@patch("gargbot_3000.journey.map_url_for_location")
@patch("gargbot_3000.journey.poi_for_location")
def test_days_to_update(
    mock_poi_func, mock_map_url_func, mock_image_func, mock_address_func
):
    mock_poi_func.return_value = "Poi"
    mock_map_url_func.return_value = "www.mapurl"
    mock_image_func.return_value = "www.image"
    mock_address_func.return_value = "Adress"
    conn = journey.MockSQL()
    client = MockHealth()
    journey_id = insert_journey_data(conn)
    start_date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, start_date)
    journey.perform_daily_update(conn, client, journey_id, start_date)

    cur_date = start_date.add(days=2)
    itr = journey.days_to_update(conn, journey_id, cur_date)
    days = list(itr)
    assert days == [cur_date.subtract(days=1)]


@patch("gargbot_3000.journey.address_for_location")
@patch("gargbot_3000.journey.image_for_location")
@patch("gargbot_3000.journey.map_url_for_location")
@patch("gargbot_3000.journey.poi_for_location")
def test_journey_finished(
    mock_poi_func, mock_map_url_func, mock_image_func, mock_address_func
):
    mock_poi_func.return_value = "Poi"
    mock_map_url_func.return_value = "www.mapurl"
    mock_image_func.return_value = "www.image"
    mock_address_func.return_value = "Adress"
    conn = journey.MockSQL()
    client = MockHealth()
    journey_id = insert_journey_data(conn)
    start_date = pendulum.datetime(2013, 3, 31, tz="UTC")
    journey.start_journey(conn, journey_id, start_date)
    journey.perform_daily_update(conn, client, journey_id, start_date)

    cur_date = start_date.add(days=4)
    data = []
    for date in journey.days_to_update(conn, journey_id, cur_date):
        datum = journey.perform_daily_update(conn, client, journey_id, date)
        data.append(datum)
    last_loc = [datum for datum in data if datum is not None][-1]
    report, img_url, map_url = last_loc
    assert report == "Vi har ankommet reisens mål!"
