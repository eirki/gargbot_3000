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

from dotenv import load_dotenv
import geopy
from geopy.geocoders import Nominatim
import googlemaps
import gpxpy
import numpy as np
import pandas as pd
import pendulum
import requests

from gargbot_3000.logger import log

stride = 0.75
# poi_types = (
#     "accounting, airport, amusement_park, aquarium, art_gallery, atm, bakery, bank, "
#     "bar, beauty_salon, bicycle_store, book_store, bowling_alley, bus_station, "
#     "cafe, campground, car_dealer, car_rental, car_repair, car_wash, casino, cemetery, "
#     "church, city_hall, clothing_store, convenience_store, courthouse, dentist, "
#     "department_store, doctor, drugstore, electrician, electronics_store, embassy, "
#     "fire_station, florist, funeral_home, furniture_store, gas_station, gym, hair_care, "
#     "hardware_store, hindu_temple, home_goods_store, hospital, insurance_agency, "
#     "jewelry_store, laundry, lawyer, library, light_rail_station, liquor_store, "
#     "local_government_office, locksmith, lodging, meal_delivery, meal_takeaway, "
#     "mosque, movie_rental, movie_theater, moving_company, museum, night_club, painter, "
#     "park, parking, pet_store, pharmacy, physiotherapist, plumber, police, post_office, "
#     "primary_school, real_estate_agency, restaurant, roofing_contractor, rv_park, "
#     "school, secondary_school, shoe_store, shopping_mall, spa, stadium, storage, "
#     "store, subway_station, supermarket, synagogue, taxi_stand, tourist_attraction, "
#     "train_station, transit_station, travel_agency, university, veterinary_care, zoo"
# )

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


class MockHealth:
    def steps_today(self, date):
        return [
            {"gargling_id": 0, "amount": random.randrange(20_000)},
            {"gargling_id": 1, "amount": random.randrange(20_000)},
            {"gargling_id": 2, "amount": random.randrange(20_000)},
            {"gargling_id": 3, "amount": random.randrange(20_000)},
        ]


class MockSQL:
    def __init__(self):
        self._journey = pd.DataFrame(
            columns=["origin", "destination", "started_at", "finished_at"]
        )
        self._point = pd.DataFrame(columns=["journey_id", "lat", "lon", "cum_dist"])
        self._step = pd.DataFrame(
            columns=["gargling_id", "journey_id", "taken_at", "amount"]
        )
        self._location = pd.DataFrame(
            columns=[
                "journey_id",
                "lat",
                "lon",
                "distance",
                "date",
                "address",
                "img_url",
                "map_url",
                "poi",
                "latest_point",
            ]
        )

    def add_journey(self, journey: dict) -> int:
        self._journey = self._journey.append(journey, ignore_index=True,)
        journey_id = self._journey.iloc[-1].name
        return journey_id

    def start_journey(self, journey_id, date) -> None:
        self._journey.loc[journey_id, "started_at"] = date

    def finish_journey(self, journey_id, date) -> None:
        self._journey.loc[journey_id, "finished_at"] = date

    def get_ongoing_journey(self) -> dict:
        return (
            self._journey[
                self._journey["started_at"].notna()
                & self._journey["finished_at"].isna()
            ]
            .iloc[0]
            .to_dict()
        )

    def get_journey(self, journey_id):
        return self._journey.iloc[journey_id]

    def add_points(self, points) -> None:
        self._point = self._point.append(points, sort=False)

    def get_points(self, journey_id) -> pd.DataFrame:
        return self._point[self._point["journey_id"] == journey_id]

    def get_point_for_distance(self, journey_id, distance) -> dict:
        points = self.get_points(journey_id)
        point = points[distance > points["cum_dist"]].iloc[-1]
        point_dict = point.to_dict()
        point_dict["index"] = point.name
        return point_dict

    def get_next_point_for_point(self, journey_id, point_in: dict) -> t.Optional[dict]:
        points = self.get_points(journey_id)
        try:
            point = points.iloc[point_in["index"] + 1]
            point_dict = point.to_dict()
            point_dict["index"] = point.name
            return point_dict
        except IndexError:
            return None

    def add_steps(self, steps) -> None:
        self._step = self._step.append(steps, sort=False)

    def get_steps(self, journey_id):
        return self._step[self._step["journey_id"] == journey_id]

    def add_location(self, location: dict) -> None:
        self._location = self._location.append(location, ignore_index=True)

    def most_recent_location(self, journey_id) -> t.Optional[dict]:
        try:
            loc = (
                self._location[self._location["journey_id"] == journey_id]
                .iloc[-1]
                .to_dict()
            )
            ts = loc["date"]
            loc["date"] = pendulum.DateTime(
                year=ts.year,
                month=ts.month,
                day=ts.day,
                tzinfo=pendulum.tz.timezone("UTC"),
            )
            return loc
        except IndexError:
            return None


def define_journey(conn, origin, destination) -> int:
    journey = {
        "origin": origin,
        "destination": destination,
        "started_at": None,
        "finished_at": None,
    }
    journey_id = conn.add_journey(journey)
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
    conn.add_points(points)


def start_journey(conn, journey_id, date) -> None:
    conn.start_journey(journey_id, date)


def store_steps(conn, steps: pd.Series, journey_id, date) -> None:
    df = pd.DataFrame(steps)
    df["taken_at"] = date
    df["journey_id"] = journey_id
    conn.add_steps(df)


def address_for_location(lat, lon) -> t.Optional[str]:
    geolocator = Nominatim(user_agent="gargbot 3000")
    try:
        location = geolocator.reverse(f"{lat}, {lon}")
        return location.address
    except Exception as e:
        print(e)
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
    google = googlemaps.Client(key=os.environ["google_api_key"],)
    details = google.places_nearby(location=(lat, lon), radius=1000)["results"]
    pois = [d for d in details if "point_of_interest" in d.get("types", [])]
    if not pois:
        return None
    try:
        poi = next(p for p in pois if not poi_types.isdisjoint(p.get("types", [])))
        return poi["name"]
    except StopIteration:
        return None
    print(poi.get("types"))
    print(poi_types.isdisjoint(poi.get("types", [])))


def get_location(conn, journey_id, distance) -> dict:
    latest_point = conn.get_point_for_distance(journey_id, distance)
    next_point = conn.get_next_point_for_point(journey_id, latest_point)
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
        "latest_point": latest_point["index"],
        "finished": finished,
    }
    return location


def store_location(conn, journey_id, date, location: dict) -> None:
    location["journey_id"] = journey_id
    location["date"] = date
    conn.add_location(location)


def most_recent_location(conn, journey_id) -> t.Optional[dict]:
    return conn.most_recent_location(journey_id)


def completion_celebration(date, steps, journey_id) -> str:
    report = "Vi har ankommet reisens mål!"
    return report


def perform_daily_update(
    conn, client, journey_id, date
) -> t.Optional[t.Tuple[str, t.Optional[str], t.Optional[str]]]:
    journey = conn.get_journey(journey_id)
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
        conn.finish_journey(journey_id, date)
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
    journey = conn.get_journey(journey_id)
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


"""load_dotenv(dotenv_path="/home/ebs/Dropbox/Programmering/bot/gargbot_3000/.env")
conn = MockSQL()

filename = "/home/ebs/Dropbox/Programmering/bot/gargen-does-japan/denne.gpx"
origin = "Larkollen"
destination = "Yamanakako"

# setup
journey_id = define_journey(conn, origin, destination)
with open(filename) as file_obj:
    data = file_obj.read()
parse_gpx(conn, journey_id, data)
start_at = pendulum.today("UTC")
start_journey(conn, journey_id, start_at)

# update
update_at = start_at.add(days=3)
print(f"Update perfomed at {update_at}")
client = MockHealth()
for day in days_to_update(conn, journey_id, update_at):
    upd, _, _ = perform_daily_update(conn, client, journey_id, update_at)
    print(upd)

"""
