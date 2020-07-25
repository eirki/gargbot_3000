#! /usr/bin/env python3.6
# coding: utf-8
import base64
import datetime as dt
import hashlib
import hmac
from operator import itemgetter
import os
import random
import typing as t
import urllib
import urllib.parse as urlparse

import aiosql
from dotenv import load_dotenv
import geopy
from geopy.geocoders import Nominatim
import googlemaps
import gpxpy
import pendulum
from psycopg2.extensions import connection
import requests

from gargbot_3000.logger import log

stride = 0.75
queries = aiosql.from_path("sql/journey.sql", "psycopg2")

poi_types = {
    "amusement_park",
    "aquarium",
    "art_gallery",
    "bar",
    "beauty_salon",
    "bowling_alley",
    "campground",
    "casino",
    "cemetery",
    "church",
    "courthouse",
    "embassy",
    "funeral_home",
    "gym",
    "hair_care",
    "hardware_store",
    "hindu_temple",
    "library",
    "liquor_store",
    "mosque",
    "movie_theater",
    "museum",
    "night_club",
    "pet_store",
    "rv_park",
    "spa",
    "stadium",
    "synagogue",
    "tourist_attraction",
    "zoo",
}


def define_journey(conn, origin, destination) -> int:
    journey_id = queries.add_journey(conn, origin=origin, destination=destination)
    return journey_id


def parse_gpx(conn, journey_id, xml_data) -> None:
    gpx = gpxpy.parse(xml_data)
    plist = gpx.tracks[0].segments[0].points
    points: t.List[dict] = []
    prev_point = None
    cumulative_distance = 0
    for point in plist:
        if prev_point is not None:
            distance = point.distance_2d(prev_point)
            cumulative_distance += distance
        data = {
            "journey_id": journey_id,
            "lat": point.latitude,
            "lon": point.longitude,
            "cum_dist": cumulative_distance,
        }
        points.append(data)
        prev_point = point
    queries.add_points(conn, points)


def start_journey(conn: connection, journey_id: int, date: pendulum.DateTime) -> None:
    queries.start_journey(conn, journey_id=journey_id, date=date)


def store_steps(conn, steps, journey_id, date) -> None:
    for step in steps:
        step["taken_at"] = date
        step["journey_id"] = journey_id
    queries.add_steps(conn, steps)


def address_for_location(lat, lon) -> t.Optional[str]:
    geolocator = Nominatim(user_agent="gargbot 3000")
    try:
        location = geolocator.reverse(f"{lat}, {lon}")
        return location.address
    except Exception as exc:
        log.exception(exc)
        return None


def image_for_location(lat, lon) -> t.Optional[str]:
    domain = "https://maps.googleapis.com"
    endpoint = "/maps/api/streetview?"
    params = {
        "size": "400x400",
        "location": f"{lat}, {lon}",
        "fov": 80,
        "heading": 70,
        "pitch": 0,
        "key": os.environ["google_api_key"],
    }
    url_to_sign = endpoint + urllib.parse.urlencode(params)
    secret = os.environ["google_api_secret"]
    decoded_key = base64.urlsafe_b64decode(secret)
    signature = hmac.new(decoded_key, url_to_sign.encode(), hashlib.sha1)
    encoded_signature = base64.urlsafe_b64encode(signature.digest())
    params["signature"] = encoded_signature.decode()
    encoded_url = domain + endpoint + urllib.parse.urlencode(params)
    # response = requests.get(encoded_url)
    return encoded_url


def map_url_for_location(lat, lon) -> str:
    return f"http://maps.google.com/maps?q=&layer=c&cbll={lat}, {lon}"
    # return f"https://www.google.com/maps/search/?api=1&query={lat}, {lon}"


def poi_for_location(lat, lon) -> t.Optional[str]:
    try:
        google = googlemaps.Client(key=os.environ["google_api_key"])
        details = google.places_nearby(location=(lat, lon), radius=1000)["results"]
    except Exception as exc:
        log.exception(exc)
        return None
    pois = [d for d in details if "point_of_interest" in d.get("types", [])]
    if not pois:
        return None
    try:
        poi = next(p for p in pois if not poi_types.isdisjoint(p.get("types", [])))
        return poi["name"]
    except StopIteration:
        return None


def get_location(conn, journey_id, distance) -> dict:
    latest_point = queries.get_point_for_distance(
        conn, journey_id=journey_id, distance=distance
    )
    next_point = queries.get_next_point_for_point(
        conn, journey_id=journey_id, point_id=latest_point["id"]
    )
    if next_point is None:
        finished = True
        current_lat = latest_point["lat"]
        current_lon = latest_point["lon"]
    else:
        finished = False
        remaining_dist = distance - latest_point["cum_dist"]
        angle = gpxpy.geo.get_course(
            latest_point["lat"],
            latest_point["lon"],
            next_point["lat"],
            next_point["lon"],
        )
        delta = gpxpy.geo.LocationDelta(distance=remaining_dist, angle=angle)
        latest_point_obj = gpxpy.geo.Location(latest_point["lat"], latest_point["lon"])
        current_lat, current_lon = delta.move(latest_point_obj)
    address = address_for_location(current_lat, current_lon)
    img_url = image_for_location(current_lat, current_lon)
    map_url = map_url_for_location(current_lat, current_lon)
    poi = poi_for_location(current_lat, current_lon)
    location = {
        "lat": current_lat,
        "lon": current_lon,
        "distance": distance,
        "address": address,  # need to inspect data type
        "img_url": img_url,  # how to store image?
        "map_url": map_url,
        "poi": poi,
        "latest_point": latest_point["id"],
        "finished": finished,
    }
    return location


def store_location(conn, journey_id, date, loc: dict) -> None:
    queries.add_location(
        conn,
        journey_id=journey_id,
        latest_point=loc["latest_point"],
        lat=loc["lat"],
        lon=loc["lon"],
        distance=loc["distance"],
        date=date,
        address=loc["address"],
        img_url=loc["img_url"],
        map_url=loc["map_url"],
        poi=loc["poi"],
    )


def most_recent_location(conn, journey_id) -> t.Optional[dict]:
    loc = queries.most_recent_location(conn, journey_id=journey_id)
    if loc is None:
        return None
    as_dict = {
        "journey_id": loc["journey_id"],
        "latest_point": loc["latest_point"],
        "lat": loc["lat"],
        "lon": loc["lon"],
        "distance": loc["distance"],
        "date": pendulum.instance(loc["date"]),
        "address": loc["address"],
        "img_url": loc["img_url"],
        "map_url": loc["map_url"],
        "poi": loc["poi"],
    }
    return as_dict


def completion_celebration(date, steps, journey_id) -> str:
    report = "Vi har ankommet reisens mål!"
    return report


def perform_daily_update(
    conn: connection, client, journey_id: int, date: pendulum.DateTime
) -> t.Optional[t.Tuple[str, t.Optional[str], t.Optional[str]]]:
    journey = queries.get_journey(conn, journey_id=journey_id)
    if journey["finished_at"] is not None or journey["started_at"] is None:
        return None
    steps_data = client.steps_today(date)
    # steps_data = steps_func(date)
    store_steps(conn, steps_data, journey_id, date)
    last_location = most_recent_location(conn, journey_id)
    last_total_distance = last_location["distance"] if last_location else 0
    steps_today = sum(data["amount"] for data in steps_data)
    if steps_today == 0:
        return None
    distance_today = steps_today * stride
    distance = distance_today + last_total_distance
    loc = get_location(conn, journey_id, distance)
    store_location(conn, journey_id, date, loc)
    steps_summary = ", ".join(
        [
            f"{row['gargling_id']}: {row['amount']}"
            for row in sorted(steps_data, key=itemgetter("amount"), reverse=True)
        ]
    )
    if loc.pop("finished"):
        queries.finish_journey(conn, journey_id=journey_id, date=date)
        return (
            completion_celebration(date, steps_summary, journey_id),
            loc["img_url"],
            loc["map_url"],
        )
    poi = f"Kveldens underholdning: {loc['poi']}\n" if loc["poi"] else ""
    report = (
        f"Daily report for {date.day}.{date.month}.{date.year}:\n"
        f"Steps taken: {steps_summary}\n"
        f"Distance travelled: {round(distance_today / 1000, 1)} km\n"
        f"Distance travelled totalt: {round(distance / 1000, 1)} km\n"
        f"Address: {loc['address']}\n"
        f"{poi}"
    )
    return report, loc["img_url"], loc["map_url"]


def days_to_update(conn, journey_id, date) -> t.Iterable[dt.datetime]:
    journey = queries.get_journey(conn, journey_id=journey_id)
    start_loc = most_recent_location(conn, journey_id)
    if start_loc is None:
        last_updated_at = journey["started_at"]
    else:
        last_updated_at = start_loc["date"].add(days=1)
        # add one day because (date-date) returns that date
    period_to_add = date - last_updated_at
    for day in period_to_add:
        if day == date:
            # to not perform update if day is not finished
            continue
        yield day


def main(
    conn, steps_func: t.Callable
) -> t.List[t.Tuple[str, t.Optional[str], t.Optional[str]]]:
    ongoing_journey = conn.get_ongoing_journey()
    journey_id = ongoing_journey["journey_id"]
    current_date = pendulum.now("UTC")
    data = []
    for date in days_to_update(conn, journey_id, current_date):
        try:
            datum = perform_daily_update(conn, steps_func, journey_id, date)
            if datum:
                data.append(datum)
        except Exception as exc:
            log.exception(exc)
    return data
