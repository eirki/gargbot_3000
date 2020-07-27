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
from dropbox import Dropbox
from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import jwt_required
import geopy
from geopy.geocoders import Nominatim
import googlemaps
import gpxpy
import pendulum
from psycopg2.extensions import connection
import requests

from gargbot_3000 import config, database, health
from gargbot_3000.logger import log

stride = 0.75
queries = aiosql.from_path("sql/journey.sql", "psycopg2")
blueprint = Blueprint("journey", __name__)

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


@blueprint.route("/list_journeys")
@jwt_required
def list_journeys():
    with current_app.pool.get_connection() as conn:
        journeys = queries.all_journeys(conn)
        journeys = [dict(journey) for journey in journeys]
    return jsonify(journeys=journeys)


@blueprint.route("/upload_journey", methods=["POST"])
@jwt_required
def handle_journey_upload():
    origin = request.form["origin"]
    dest = request.form["dest"]
    xmlfile = request.files["file"]
    with current_app.pool.get_connection() as conn:
        journey_id = define_journey(conn, origin, dest)
        parse_gpx(conn, journey_id, xmlfile)
        conn.commit()
    return Response(status=200)


@blueprint.route("/start_journey")
@jwt_required
def handle_start_journey():
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        date = pendulum.now()
        start_journey(conn, journey_id, date)
        conn.commit()
    return Response(status=200)


@blueprint.route("/stop_journey")
@jwt_required
def stop_journey():
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        queries.stop_journey(conn, journey_id=journey_id)
        conn.commit()
    return Response(status=200)


@blueprint.route("/delete_journey")
@jwt_required
def delete_journey():
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        queries.delete_journey(conn, journey_id=journey_id)
        conn.commit()
    return Response(status=200)


def define_journey(conn, origin, destination) -> int:
    journey_id = queries.add_journey(conn, origin=origin, destination=destination)
    return journey_id


def parse_gpx(conn, journey_id, xml_data) -> None:
    gpx = gpxpy.parse(xml_data)
    plist = gpx.tracks[0].segments[0].points
    waypoints: t.List[dict] = []
    prev_waypoint = None
    cumulative_distance = 0
    for waypoint in plist:
        if prev_waypoint is not None:
            distance = waypoint.distance_2d(prev_waypoint)
            cumulative_distance += distance
        data = {
            "journey_id": journey_id,
            "lat": waypoint.latitude,
            "lon": waypoint.longitude,
            "cum_dist": cumulative_distance,
        }
        waypoints.append(data)
        prev_waypoint = waypoint
    queries.add_waypoints(conn, waypoints)


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


def image_for_location(lat, lon, journey_id: int, waypoint_id: int) -> t.Optional[str]:
    domain = "https://maps.googleapis.com"
    endpoint = "/maps/api/streetview?"
    params = {
        "size": "400x400",
        "location": f"{lat}, {lon}",
        "fov": 80,
        "heading": 251.74,
        "pitch": 0,
        "key": config.google_api_key,
    }
    url_to_sign = endpoint + urllib.parse.urlencode(params)
    secret = config.google_api_secret
    decoded_key = base64.urlsafe_b64decode(secret)
    signature = hmac.new(decoded_key, url_to_sign.encode(), hashlib.sha1)
    encoded_signature = base64.urlsafe_b64encode(signature.digest())
    params["signature"] = encoded_signature.decode()
    encoded_url = domain + endpoint + urllib.parse.urlencode(params)
    try:
        response = requests.get(encoded_url)
        data = response.content
    except Exception:
        log.error("Error downloading streetview image", exc_info=True)
        return None

    dbx = Dropbox(config.dropbox_token)
    upload_path = config.dbx_journey_folder / f"{journey_id}_{waypoint_id}.jpg"
    try:
        uploaded = dbx.files_upload(
            f=data, path=upload_path.as_posix(), autorename=True
        )
    except Exception:
        log.error("Error uploading streetview image", exc_info=True)
        return None
    shared = dbx.sharing_create_shared_link(uploaded.path_display)
    url = shared.url.replace("?dl=0", "?raw=1")
    return url


def map_url_for_location(lat, lon) -> str:
    return f"https://www.google.com/maps/@?api=1&map_action=pano&fov=80&heading=251.74&pitch=0&viewpoint={lat}, {lon}"
    # return f"http://maps.google.com/maps?q=&layer=c&cbll={lat}, {lon}"
    # return f"https://www.google.com/maps/search/?api=1&query={lat}, {lon}"


def poi_for_location(lat, lon) -> t.Optional[str]:
    try:
        google = googlemaps.Client(key=config.google_api_key)
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
    latest_waypoint = queries.get_waypoint_for_distance(
        conn, journey_id=journey_id, distance=distance
    )
    next_waypoint = queries.get_next_waypoint_for_waypoint(
        conn, journey_id=journey_id, waypoint_id=latest_waypoint["id"]
    )
    if next_waypoint is None:
        finished = True
        current_lat = latest_waypoint["lat"]
        current_lon = latest_waypoint["lon"]
    else:
        finished = False
        remaining_dist = distance - latest_waypoint["cum_dist"]
        angle = gpxpy.geo.get_course(
            latest_waypoint["lat"],
            latest_waypoint["lon"],
            next_waypoint["lat"],
            next_waypoint["lon"],
        )
        delta = gpxpy.geo.LocationDelta(distance=remaining_dist, angle=angle)
        latest_waypoint_obj = gpxpy.geo.Location(
            latest_waypoint["lat"], latest_waypoint["lon"]
        )
        current_lat, current_lon = delta.move(latest_waypoint_obj)
    address = address_for_location(current_lat, current_lon)
    img_url = image_for_location(
        current_lat,
        current_lon,
        journey_id=journey_id,
        waypoint_id=latest_waypoint["id"],
    )
    map_url = map_url_for_location(current_lat, current_lon)
    poi = poi_for_location(current_lat, current_lon)
    location = {
        "lat": current_lat,
        "lon": current_lon,
        "distance": distance,
        "journey_distance": latest_waypoint["journey_distance"],
        "address": address,  # need to inspect data type
        "img_url": img_url,  # how to store image?
        "map_url": map_url,
        "poi": poi,
        "latest_waypoint": latest_waypoint["id"],
        "finished": finished,
    }
    return location


def store_location(conn, journey_id, date, loc: dict) -> None:
    queries.add_location(
        conn,
        journey_id=journey_id,
        latest_waypoint=loc["latest_waypoint"],
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
        "latest_waypoint": loc["latest_waypoint"],
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


def format_response(
    date: pendulum.DateTime,
    steps_data: dict,
    dist_today: int,
    dist_total: int,
    dist_remaining: int,
    address: t.Optional[str],
    poi: t.Optional[str],
    img_url: t.Optional[str],
    map_url: str,
    weight_reports: t.List[str],
    finished: bool,
) -> dict:
    blocks = []
    title_txt = (
        f"*Ekspedisjonsrapport for {date.day}.{date.month}.{date.year}*"
        if not finished
        else "*Ekspedisjon complete!*"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": title_txt}})

    sorted_steps_data = sorted(steps_data, key=itemgetter("amount"), reverse=True)
    steps_txt = "Steps taken:"
    for i, row in enumerate(sorted_steps_data):
        if i == 0:
            amount = f"*{row['amount']}* :star:"
        elif i == len(steps_data) - 1:
            amount = f"_{row['amount']}_"
        else:
            amount = str(row["amount"])
        desc = f"\n\t• {row['first_name']}: {amount}"
        steps_txt += desc
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": steps_txt}})

    distance_txt = (
        f"I går gikk vi {dist_today} km. "
        f"Vi har gått {dist_total} km totalt på vår journey, "
        f"og har igjen {dist_remaining} km til vi er fremme."
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": distance_txt}})

    location_txt = ""
    if address is not None:
        location_txt += f"Vi har nå kommet til {address}. "
    if poi is not None:
        location_txt += f"Kveldens underholdning er {poi}."
    if location_txt:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": location_txt}}
        )

    if img_url is not None:
        alt_text = address if address is not None else "Check it!"
        blocks.append({"type": "image", "image_url": img_url, "alt_text": alt_text})

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{map_url}|Se deg litt rundt da vel!>",
            },
        }
    )

    blocks.append({"type": "divider"})

    if weight_reports:
        weight_txt = "\n\n".join(weight_reports)
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Also: {weight_txt}"},
            }
        )

    response = {"text": title_txt, "blocks": blocks}
    return response


def perform_daily_update(
    conn: connection,
    activity_func: t.Callable,
    journey_id: int,
    date: pendulum.DateTime,
) -> t.Optional[dict]:
    journey = queries.get_journey(conn, journey_id=journey_id)
    if journey["finished_at"] is not None or journey["started_at"] is None:
        return None
    steps_data, weight_reports = activity_func(conn, date)
    store_steps(conn, steps_data, journey_id, date)
    last_location = most_recent_location(conn, journey_id)
    last_total_distance = last_location["distance"] if last_location else 0
    steps_today = sum(data["amount"] for data in steps_data)
    if steps_today == 0:
        return None
    distance_today = steps_today * stride
    distance_total = distance_today + last_total_distance
    loc = get_location(conn, journey_id, distance_total)
    dist_remaining = loc["journey_distance"] - distance_total
    store_location(conn, journey_id, date, loc)
    finished = loc.pop("finished")
    if finished:
        queries.finish_journey(conn, journey_id=journey_id, date=date)
    return {
        "date": date,
        "steps_data": steps_data,
        "dist_today": round(distance_today / 1000, 1),
        "dist_total": round(distance_total / 1000, 1),
        "dist_remaining": round(dist_remaining / 1000, 1),
        "address": loc["address"],
        "poi": loc["poi"],
        "img_url": loc["img_url"],
        "map_url": loc["map_url"],
        "weight_reports": weight_reports,
        "finished": finished,
    }


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


def main(conn) -> t.List[dict]:
    ongoing_journey = queries.get_ongoing_journey(conn)
    journey_id = ongoing_journey["id"]
    current_date = pendulum.now("UTC")
    data = []
    for date in days_to_update(conn, journey_id, current_date):
        try:
            datum = perform_daily_update(
                conn=conn,
                activity_func=health.activity,
                journey_id=journey_id,
                date=date,
            )
            if datum:
                formatted = format_response(**datum)
                data.append(formatted)
        except Exception as exc:
            log.exception(exc)
    return data
