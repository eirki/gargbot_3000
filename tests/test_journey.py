#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from contextlib import contextmanager
from operator import itemgetter
from unittest.mock import patch

from PIL import Image
from flask.testing import FlaskClient
import pendulum
import psycopg2
from psycopg2.extensions import connection
import pytest

from gargbot_3000 import config
from gargbot_3000.journey import journey, mapping

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
    {"lat": 47.586392, "lon": 40.688998, "distance": 0.000000, "elevation": 1},
    {"lat": 47.586482, "lon": 40.690648, "distance": 124.290397, "elevation": 1},
    {"lat": 47.586346, "lon": 40.692903, "distance": 294.277151, "elevation": 2},
    {"lat": 47.586119, "lon": 40.694385, "distance": 408.383249, "elevation": 4},
    {"lat": 47.585707, "lon": 40.695735, "distance": 519.639149, "elevation": 5},
    {"lat": 47.582350, "lon": 40.704350, "distance": 1266.708526, "elevation": 1},
    {"lat": 47.581214, "lon": 40.707144, "distance": 1511.674758, "elevation": 1},
    {"lat": 47.580374, "lon": 40.708726, "distance": 1662.856365, "elevation": 1},
    {"lat": 47.579466, "lon": 40.710005, "distance": 1802.287666, "elevation": 1},
    {"lat": 47.577354, "lon": 40.712160, "distance": 2087.707336, "elevation": 2},
    {"lat": 47.549180, "lon": 40.750911, "distance": 6367.173839, "elevation": 6},
    {"lat": 47.523033, "lon": 40.764962, "distance": 9463.573534, "elevation": 9},
    {"lat": 47.427366, "lon": 41.011354, "distance": 30843.651920, "elevation": 3},
    {"lat": 47.327962, "lon": 41.309018, "distance": 55862.151884, "elevation": 5},
]


def insert_journey_data(conn) -> int:
    journey_id = journey.define_journey(
        conn, origin="Origin", destination="Destination"
    )
    data_in: list[dict] = [{"journey_id": journey_id, **d} for d in gps_data]
    journey.queries.add_waypoints(conn, data_in)
    return journey_id


def example_activity_data():
    steps_data = [
        {"gargling_id": 6, "amount": 17782},
        {"gargling_id": 2, "amount": 11521},
        {"gargling_id": 3, "amount": 6380},
        {"gargling_id": 5, "amount": 111},
    ]
    body_reports = ["name2 veier 60 kg"]
    return steps_data, body_reports


def example_gargling_info() -> dict:
    infos = [
        (6, "#42d4f4", "cyan", "name6"),
        (2, "#3cb44b", "green", "name2"),
        (3, "#f58231", "orange", "name3"),
        (5, "#911eb4", "purple", "name5"),
    ]
    infodict = {
        id_: {
            "first_name": first_name,
            "color_name": color_name,
            "color_hex": color_hex,
        }
        for id_, color_hex, color_name, first_name in infos
    }
    return infodict


def example_update_data() -> dict:
    date = pendulum.Date(2013, 3, 31)
    return {
        "date": date,
        "address": "Address",
        "country": "Country",
        "poi": "Poi",
        "photo_url": "www.image",
        "map_url": "www.mapurl",
        "map_img_url": "www.tmap",
        "finished": False,
    }


@contextmanager
def api_mocker():
    with patch("gargbot_3000.journey.location_apis.main") as apis, patch(
        "gargbot_3000.journey.mapping.main"
    ) as maps, patch("gargbot_3000.journey.journey.upload_images") as upload:
        apis.return_value = (
            "Address",
            "Country",
            b"photo",
            "www.mapurl",
            "Poi",
        )
        maps.return_value = b"map"
        upload.return_value = "www.image", "www.tmap"
        yield


@patch("gargbot_3000.health.health.get_jwt_identity")
@patch("flask_jwt_extended.view_decorators.verify_jwt_in_request")
def test_list_journeys(
    mock_jwt_required, mock_jwt_identity, client: FlaskClient, conn: connection
):
    journey_id = insert_journey_data(conn)
    date1 = pendulum.Date(2013, 3, 31)
    location1 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 300,
        "latest_waypoint": 2,
        "address": "address1",
        "country": "Country1",
        "photo_url": "image1",
        "map_url": "map_url1",
        "map_img_url": "tmap_url1",
        "poi": "poi1",
    }

    date2 = pendulum.Date(2013, 4, 10)
    location2 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 301,
        "latest_waypoint": 3,
        "address": "address2",
        "country": "Country2",
        "photo_url": "image2",
        "map_url": "map_url2",
        "map_img_url": "tmap_url2",
        "poi": "poi2",
    }
    journey.queries.add_location(conn, journey_id=journey_id, date=date1, **location1)
    journey.queries.add_location(conn, journey_id=journey_id, date=date2, **location2)
    response = client.get("/list_journeys")
    assert len(response.json["journeys"]) == 1


def test_detail_journey(client: FlaskClient, conn: connection):
    journey_id = insert_journey_data(conn)
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
    with api_mocker():
        data = journey.perform_daily_update(conn, journey_id, date, steps_data, g_info)
    assert data is not None
    location, *_, finished = data
    journey.store_update_data(conn, location, finished)
    response = client.get(f"/detail_journey/{journey_id}")
    waypoints = response.json.pop("waypoints")
    length = len(waypoints["coordinates"]) - 1
    exp = [[d["lon"], d["lat"], d["elevation"]] for d in gps_data[:length]]
    assert waypoints["coordinates"][:length] == exp
    loc = journey.most_recent_location(conn, journey_id)
    assert loc is not None
    assert waypoints["coordinates"][length][0] == pytest.approx(loc["lon"])
    assert waypoints["coordinates"][length][1] == pytest.approx(loc["lat"])
    expected = {
        "destination": "Destination",
        "distance": 55862.151884,
        "finished_at": None,
        "id": 1,
        "locations": [
            {
                "address": "Address",
                "country": "Country",
                "date": "Sun, 31 Mar 2013 00:00:00 GMT",
                "distance": 26845.5,
                "journey_id": 1,
                "lat": 47.445256107266275,
                "latest_waypoint": 12,
                "lon": 40.965460224508455,
                "photo_url": None,
                "poi": "Poi",
            }
        ],
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


def test_coordinates_for_distance(conn: connection):
    journey_id = insert_journey_data(conn)
    lat, lon, latest_waypoint, finished = journey.coordinates_for_distance(
        conn, journey_id, distance=300
    )
    assert lat == pytest.approx(47.58633461507472)
    assert lon == pytest.approx(40.69297732817553)
    assert latest_waypoint == 3
    assert finished is False


def test_store_get_most_recent_location(conn):
    journey_id = insert_journey_data(conn)
    date1 = pendulum.Date(2013, 3, 31)
    location1 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 300,
        "latest_waypoint": 2,
        "address": "address1",
        "country": "Country1",
        "poi": "poi1",
    }

    date2 = pendulum.Date(2013, 4, 10)
    location2 = {
        "lat": 47.58633461507472,
        "lon": 40.69297732817553,
        "distance": 301,
        "latest_waypoint": 3,
        "address": "address2",
        "country": "Country2",
        "poi": "poi2",
        "photo_url": None,
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
    date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
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
    date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id1, date=date)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        journey.queries.start_journey(conn, journey_id=journey_id2, date=date)


def test_store_steps(conn: connection):
    journey_id = insert_journey_data(conn)
    date = pendulum.Date(2013, 3, 31)
    data_in, _ = example_activity_data()
    journey.store_steps(conn, data_in, journey_id, date)
    data_out = journey.queries.get_steps(conn, journey_id=journey_id)
    data_out = [dict(d) for d in data_out]
    data_in.sort(key=itemgetter("gargling_id"))
    data_out.sort(key=itemgetter("gargling_id"))
    assert len(data_in) == len(data_out)
    for d_in, d_out in zip(data_in, data_out):
        d_out.pop("first_name")
        d_out.pop("color_hex")
        assert d_in == d_out


def test_store_steps_twice_fails(conn: connection):
    journey_id = insert_journey_data(conn)
    date = pendulum.Date(2013, 3, 31)
    steps_data, _ = example_activity_data()
    journey.store_steps(conn, steps_data, journey_id, date)
    with pytest.raises(psycopg2.errors.UniqueViolation):
        journey.store_steps(conn, steps_data, journey_id, date)


def test_daily_update(conn: connection):
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    journey_id = insert_journey_data(conn)
    date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
    with api_mocker():
        data = journey.perform_daily_update(conn, journey_id, date, steps_data, g_info)
    assert data is not None
    (
        location,
        distance_today,
        journey_data,
        photo_url,
        map_url,
        map_img_url,
        new_country,
        finished,
    ) = data
    expected_distance_today = 26845.5
    assert distance_today == expected_distance_today
    expected_journey_data = {
        "id": 1,
        "origin": "Origin",
        "destination": "Destination",
        "ongoing": True,
        "started_at": pendulum.date(2013, 3, 31),
        "finished_at": None,
        "distance": 55862.151884,
    }
    assert journey_data == expected_journey_data
    expected = example_update_data()
    assert photo_url == expected.pop("photo_url")
    assert map_url == expected.pop("map_url")
    assert map_img_url == expected.pop("map_img_url")
    assert finished == expected.pop("finished")
    expected["journey_id"] = 1
    expected["lat"] = 47.445256107266275
    expected["latest_waypoint"] = 12
    expected["lon"] = 40.965460224508455
    expected["distance"] = 26845.5
    assert location == expected


def test_factoid_remaining_distance():
    conn = None
    journey_data = {
        "destination": "Destination",
        "started_at": pendulum.date(2013, 3, 31),
        "distance": 10_000,
    }
    distance_today = 1000
    distance_total = 2000
    date = pendulum.date(2013, 3, 31)
    assert date.day_of_week == pendulum.SUNDAY
    factoid = journey.daily_factoid(
        date, conn, journey_data, distance_today, distance_total
    )
    exp = "Vi gikk *1 km*! Nå har vi gått 2 km totalt på vår journey til Destination. Vi har 8 km igjen til vi er framme."
    assert factoid == exp


def test_factoid_eta_average():
    conn = None
    journey_data = {
        "destination": "Destination",
        "started_at": pendulum.date(2013, 3, 29),
        "distance": 10_000,
    }
    distance_today = 1000
    distance_total = 2000
    date = pendulum.date(2013, 4, 1)
    assert date.day_of_week == pendulum.MONDAY
    factoid = journey.daily_factoid(
        date, conn, journey_data, distance_today, distance_total
    )
    exp = "Vi gikk *1 km*! Average daglig progress er 500 m. Holder vi dette tempoet er vi fremme i Destination 17. april 2013, om 16 dager."
    assert factoid == exp


def test_factoid_eta_today():
    conn = None
    journey_data = {
        "destination": "Destination",
        "started_at": pendulum.date(2013, 3, 31),
        "distance": 10_000,
    }
    distance_today = 1000
    distance_total = 2000
    date = pendulum.date(2013, 4, 2)
    assert date.day_of_week == pendulum.TUESDAY
    factoid = journey.daily_factoid(
        date, conn, journey_data, distance_today, distance_total
    )
    exp = "Vi gikk *1 km*! Hadde vi gått den distansen hver dag ville journeyen vart til 10. april 2013."
    assert factoid == exp


def test_factoid_weekly_summary(conn: connection):
    journey_id = insert_journey_data(conn)
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    date = pendulum.date(2013, 4, 6)
    assert date.day_of_week == pendulum.SATURDAY
    journey.queries.start_journey(
        conn, journey_id=journey_id, date=date.subtract(days=1)
    )
    journey.store_steps(conn, steps_data, journey_id, date.subtract(days=1))
    journey.store_steps(conn, steps_data, journey_id, date)
    with api_mocker():
        data = journey.perform_daily_update(conn, journey_id, date, steps_data, g_info)
    assert data is not None
    (
        location,
        distance_today,
        journey_data,
        photo_url,
        map_url,
        map_img_url,
        new_country,
        finished,
    ) = data
    factoid = journey.daily_factoid(
        date, conn, journey_data, distance_today, location["distance"],
    )
    exp = "Vi gikk *26.8 km*! Denne uken har vi gått 53.7 km til sammen. Garglingen som gikk lengst var name6, med 26.7 km!"
    assert factoid == exp


def test_format_response():
    g_info = example_gargling_info()
    data = example_update_data()
    steps_data, body_reports = example_activity_data()
    data["destination"] = "Destinasjon"
    factoid = "Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme."
    formatted = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement="New record!",
        factoid=factoid,
        **data,
    )
    expected = {
        "text": "Ekspedisjonsrapport 31.3.2013 - dag 8: Vi gikk 26.8 km!",
        "blocks": [
            {
                "text": {
                    "text": "*Ekspedisjonsrapport 31.3.2013 - dag 8*",
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {"text": {"text": factoid, "type": "mrkdwn"}, "type": "section"},
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
            {"type": "section", "text": {"type": "mrkdwn", "text": "New record!"}},
            {"alt_text": "Breakdown!", "image_url": "www.tmap", "type": "image"},
            {
                "text": {
                    "text": (
                        "Velkommen til Country! :confetti_ball: Vi har nå "
                        "kommet til Address. Kveldens underholdning er Poi."
                    ),
                    "type": "mrkdwn",
                },
                "type": "section",
            },
            {"alt_text": "Address", "image_url": "www.image", "type": "image"},
            {
                "text": {
                    "text": "<www.mapurl|Gøggle Maps> | "
                    f"<{config.server_name}/map|Gargbot Kart> | "
                    f"<{config.server_name}/dashboard|Stats>",
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


def test_format_response_no_address_no_country():
    data = example_update_data()
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    data["destination"] = "Destinasjon"

    data["address"] = None
    data["country"] = None
    response = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement=None,
        factoid="Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme.",
        **data,
    )
    address_block = response["blocks"][4]
    expected_address = {
        "text": {"text": "Kveldens underholdning er Poi.", "type": "mrkdwn"},
        "type": "section",
    }
    img_block = response["blocks"][5]
    expected_img = {"alt_text": "Check it!", "image_url": "www.image", "type": "image"}
    assert address_block == expected_address
    assert img_block == expected_img


def test_format_response_no_address():
    data = example_update_data()
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    data["destination"] = "Destinasjon"

    data["address"] = None
    response = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement=None,
        factoid="Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme.",
        **data,
    )
    address_block = response["blocks"][4]
    expected_address = {
        "text": {
            "text": "Velkommen til Country! :confetti_ball: Kveldens underholdning er Poi.",
            "type": "mrkdwn",
        },
        "type": "section",
    }
    img_block = response["blocks"][5]
    expected_img = {"alt_text": "Check it!", "image_url": "www.image", "type": "image"}
    assert address_block == expected_address
    assert img_block == expected_img


def test_format_response_no_country():
    data = example_update_data()
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    data["destination"] = "Destinasjon"

    data["country"] = None
    response = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement=None,
        factoid="Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme.",
        **data,
    )
    address_block = response["blocks"][4]
    expected_address = {
        "text": {
            "text": "Vi har nå kommet til Address. Kveldens underholdning er Poi.",
            "type": "mrkdwn",
        },
        "type": "section",
    }
    img_block = response["blocks"][5]
    expected_img = {"alt_text": "Address", "image_url": "www.image", "type": "image"}
    assert address_block == expected_address
    assert img_block == expected_img


def test_format_response_nopoi():
    data = example_update_data()
    steps_data, body_reports = example_activity_data()

    g_info = example_gargling_info()
    data["destination"] = "Destinasjon"

    data["poi"] = None

    response = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement=None,
        factoid="Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme.",
        **data,
    )
    address_block = response["blocks"][4]
    expected = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Velkommen til Country! :confetti_ball: Vi har nå kommet til Address. ",
        },
    }
    assert address_block == expected


def test_format_response_no_photo_url():
    data = example_update_data()
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()

    data["destination"] = "Destinasjon"

    data["photo_url"] = None
    response = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement=None,
        factoid="Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme.",
        **data,
    )
    assert len(response["blocks"]) == 8


def test_format_response_no_all():
    data = example_update_data()
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()

    data["destination"] = "Destinasjon"

    data["address"] = None
    data["country"] = None
    data["poi"] = None
    data["photo_url"] = None
    data["map_img_url"] = None
    response = journey.format_response(
        n_day=8,
        gargling_info=g_info,
        steps_data=steps_data,
        body_reports=body_reports,
        achievement=None,
        factoid="Vi gikk *26.8 km*! Nå har vi gått 26.8 km totalt, vi har 29 km igjen til vi er framme.",
        **data,
    )
    assert len(response["blocks"]) == 6


def test_days_to_update_unstarted(conn):
    journey_id = insert_journey_data(conn)
    date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
    next_date = date.add(days=1)
    itr = journey.days_to_update(conn, journey_id, next_date)
    days = list(itr)
    assert days == [date]


def test_days_to_update_unstarted_two_days(conn):
    journey_id = insert_journey_data(conn)
    date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=date)
    next_date = date.add(days=2)
    itr = journey.days_to_update(conn, journey_id, next_date)
    days = list(itr)
    assert days == [date, date.add(days=1)]


def test_days_to_update(conn: connection):
    steps_data, body_reports = example_activity_data()
    g_info = example_gargling_info()
    journey_id = insert_journey_data(conn)
    start_date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=start_date)
    with api_mocker():
        data = journey.perform_daily_update(
            conn, journey_id, start_date, steps_data, g_info
        )
    assert data is not None
    location, *_, finished = data
    journey.store_update_data(conn, location, finished)
    cur_date = start_date.add(days=2)
    itr = journey.days_to_update(conn, journey_id, cur_date)
    days = list(itr)
    assert days == [cur_date.subtract(days=1)]


@patch("gargbot_3000.health.activity")
def test_journey_finished(mock_activity, conn: connection):
    steps_data, body_reports = example_activity_data()
    mock_activity.return_value = (steps_data, body_reports)
    journey_id = insert_journey_data(conn)
    start_date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=start_date)
    g_info = example_gargling_info()
    with api_mocker():
        steps_data, body_reports = example_activity_data()
        journey.perform_daily_update(conn, journey_id, start_date, steps_data, g_info)
        cur_date = start_date.add(days=4)
        data = []
        for date in journey.days_to_update(conn, journey_id, cur_date):
            steps_data, body_reports = example_activity_data()
            datum = journey.perform_daily_update(
                conn, journey_id, date, steps_data, g_info
            )
            if datum is None:
                continue
            location, *_, finished = datum
            journey.store_update_data(conn, location, finished)
            data.append(finished)
        last_fin = data[-1]
    assert last_fin is True


@patch("gargbot_3000.health.activity")
def test_journey_main(
    mock_activity, conn: connection,
):
    steps_data, body_reports = example_activity_data()
    mock_activity.return_value = (steps_data, body_reports)
    journey_id = insert_journey_data(conn)
    start_date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=start_date)
    now = start_date.add(days=2)
    with api_mocker():
        dat = list(journey.main(conn, now))
    assert len(dat) == 2
    assert (
        dat[0]["blocks"][0]["text"]["text"] == "*Ekspedisjonsrapport 31.3.2013 - dag 1*"
    )
    assert (
        dat[1]["blocks"][0]["text"]["text"] == "*Ekspedisjonsrapport 1.4.2013 - dag 2*"
    )


@patch("gargbot_3000.health.activity")
def test_generate_all_maps(mock_activity, conn):
    steps_data, body_reports = example_activity_data()
    mock_activity.return_value = (steps_data, body_reports)
    journey_id = insert_journey_data(conn)
    start_date = pendulum.Date(2013, 3, 31)
    journey.queries.start_journey(conn, journey_id=journey_id, date=start_date)
    g_info = example_gargling_info()
    with api_mocker():
        journey.perform_daily_update(conn, journey_id, start_date, steps_data, g_info)
        cur_date = start_date.add(days=4)
        for date in journey.days_to_update(conn, journey_id, cur_date):
            steps_data, body_reports = example_activity_data()
            datum = journey.perform_daily_update(
                conn, journey_id, date, steps_data, g_info
            )
            if datum is None:
                continue
            location, *_, finished = datum
            journey.store_update_data(conn, location, finished)
            journey.store_steps(conn, steps_data, journey_id, date)
    with patch("gargbot_3000.journey.mapping.render_map") as maps:
        maps.return_value = Image.new("RGB", (1000, 600), (255, 255, 255))
        mapping.generate_all_maps(conn, journey_id, write=False)
