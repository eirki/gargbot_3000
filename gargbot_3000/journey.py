#! /usr/bin/env python3.6
# coding: utf-8
import base64
import datetime as dt
import hashlib
import hmac
from io import BytesIO
import itertools
from operator import itemgetter
import os
from pathlib import Path
import random
import typing as t
import urllib
import urllib.parse as urlparse

from PIL import Image, ImageChops, ImageDraw, ImageFont
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
from staticmap import CircleMarker, Line, StaticMap

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


def generate_all_maps(journey_id, conn, write=True):
    all_steps = queries.get_steps(conn, journey_id=journey_id)
    all_steps.sort(key=itemgetter("taken_at"))
    steps_for_date = {
        date: list(steps)
        for date, steps in itertools.groupby(all_steps, lambda step: step["taken_at"])
    }
    locations = queries.locations_for_journey(conn, journey_id=journey_id)
    last_location = None
    for location in locations:
        date = location["date"]
        steps_data = steps_for_date[date]
        steps_data.sort(key=itemgetter("amount"), reverse=True)
        gargling_info = get_colors_names(
            conn, ids=[gargling["gargling_id"] for gargling in steps_data]
        )
        img = generate_traversal_map(
            conn=conn,
            journey_id=journey_id,
            last_location=last_location,
            current_lat=location["lat"],
            current_lon=location["lon"],
            current_distance=location["distance"],
            steps_data=steps_data,
            gargling_info=gargling_info,
        )
        if img is not None and write is True:
            with open((Path.cwd() / date.isoformat()).with_suffix((".jpg")), "wb") as f:
                f.write(img)
        last_location = location


@blueprint.route("/detail_journey/<journey_id>")
def detail_journey(journey_id):
    with current_app.pool.get_connection() as conn:
        j = queries.get_journey(conn, journey_id=journey_id)
        most_recent = most_recent_location(conn, journey_id)
        if most_recent is None:
            return jsonify(waypoints=[])

        waypoints = queries.waypoints_between_distances(
            conn, journey_id=journey_id, low=0, high=most_recent["distance"]
        )
        waypoints = [dict(point) for point in waypoints]
        waypoints.append(
            {
                "lat": most_recent["lat"],
                "lon": most_recent["lon"],
                "cum_dist": most_recent["distance"],
            }
        )
    return jsonify(waypoints=waypoints, **dict(j))


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


def start_journey(conn: connection, journey_id: int, date: pendulum.Date) -> None:
    queries.start_journey(conn, journey_id=journey_id, date=date)


def get_colors_names(conn: connection, ids: t.List[int]) -> t.Dict[int, dict]:
    infos = queries.colors_names_for_ids(conn, ids=ids)
    infodict = {
        info["id"]: {
            "first_name": info["first_name"],
            "color_name": info["color_name"],
            "color_hex": info["color_hex"],
        }
        for info in infos
    }
    return infodict
    infodict = {}
    for info in infos:
        gargling_id = info["id"]
        del info["id"]
        infodict[gargling_id] = dict(info)


def address_for_location(lat, lon) -> t.Optional[str]:
    geolocator = Nominatim(user_agent=config.bot_name)
    try:
        location = geolocator.reverse(f"{lat}, {lon}")
        return location.address
    except Exception:
        log.error("Error getting address for location", exc_info=True)
        return None


def image_for_location(lat, lon) -> t.Optional[bytes]:
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
    return data


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


def location_between_waypoints(
    first_waypoint, last_waypoint, distance: float
) -> t.Tuple[float, float]:
    angle = gpxpy.geo.get_course(
        first_waypoint["lat"],
        first_waypoint["lon"],
        last_waypoint["lat"],
        last_waypoint["lon"],
    )
    delta = gpxpy.geo.LocationDelta(distance=distance, angle=angle)
    first_waypoint_obj = gpxpy.geo.Location(
        first_waypoint["lat"], first_waypoint["lon"]
    )
    current_lat, current_lon = delta.move(first_waypoint_obj)
    return current_lat, current_lon


def get_location(conn, journey_id, distance) -> t.Tuple[float, float, int, bool]:
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
        current_lat, current_lon = location_between_waypoints(
            latest_waypoint, next_waypoint, remaining_dist
        )
    return current_lat, current_lon, latest_waypoint["id"], finished


def data_for_location(
    lat: float, lon: float
) -> t.Tuple[
    t.Optional[str], t.Optional[bytes], str, t.Optional[str],
]:
    address = address_for_location(lat, lon)
    street_view_img = image_for_location(lat, lon)
    map_url = map_url_for_location(lat, lon)
    poi = poi_for_location(lat, lon)
    return address, street_view_img, map_url, poi


def get_detailed_coords(current_waypoints, last_location, steps_data, start_dist):
    detailed_coords: t.List[dict] = []
    waypoints_itr = iter(current_waypoints)
    # starting location
    latest_waypoint = (
        last_location if last_location is not None else current_waypoints[0]
    )
    current_distance = start_dist
    next_waypoint = None
    for gargling in steps_data:
        gargling_coords = []
        gargling_coords.append((latest_waypoint["lon"], latest_waypoint["lat"],))
        gargling_distance = gargling["amount"] * stride
        current_distance += gargling_distance
        while True:
            if next_waypoint is None or next_waypoint["cum_dist"] < current_distance:
                # next_waypoint from previous garglings has been passed
                next_waypoint = next(waypoints_itr, None)
                if next_waypoint is None:
                    # this shouldn't really happen
                    break

            if next_waypoint["cum_dist"] < current_distance:
                # next_waypoint passed by this gargling
                gargling_coords.append((next_waypoint["lon"], next_waypoint["lat"]))
                latest_waypoint = next_waypoint
                continue
            elif next_waypoint["cum_dist"] >= current_distance:
                # next_waypoint will not be passed by this gargling
                remaining_dist = current_distance - latest_waypoint["cum_dist"]
                last_lat, last_lon = location_between_waypoints(
                    latest_waypoint, next_waypoint, remaining_dist
                )
                gargling_coords.append((last_lon, last_lat))
                # assign starting location for next gargling
                latest_waypoint = {
                    "lat": last_lat,
                    "lon": last_lon,
                    "cum_dist": current_distance,
                }
                break
        detailed_coords.append(
            {"gargling_id": gargling["gargling_id"], "coords": gargling_coords}
        )
    return detailed_coords


def traversal_data(
    conn: connection,
    journey_id: int,
    last_location: t.Optional[dict],
    current_lat: float,
    current_lon: float,
    current_distance: float,
    steps_data: t.List[dict],
) -> t.Tuple[
    t.List[t.Tuple[float, float]],
    t.List[t.Tuple[float, float]],
    t.List[t.Tuple[float, float]],
    t.List[dict],
]:
    if last_location is not None:
        old_waypoints = queries.waypoints_between_distances(
            conn, journey_id=journey_id, low=0, high=last_location["distance"]
        )
        old_coords = [(loc["lon"], loc["lat"]) for loc in old_waypoints]
        old_coords.append((last_location["lon"], last_location["lat"]))
        locations = queries.location_between_distances(
            conn, journey_id=journey_id, low=0, high=last_location["distance"]
        )
        location_coordinates = [(old_waypoints[0]["lon"], old_waypoints[0]["lat"])]
        location_coordinates.extend([(loc["lon"], loc["lat"]) for loc in locations])
        start_dist = last_location["distance"]
        overview_coords = [(last_location["lon"], last_location["lat"])]
    else:
        old_coords = []
        location_coordinates = []
        start_dist = 0
        overview_coords = []

    current_waypoints = queries.waypoints_between_distances(
        conn, journey_id=journey_id, low=start_dist, high=current_distance
    )
    current_waypoints.append(
        {"lat": current_lat, "lon": current_lon, "cum_dist": current_distance}
    )
    overview_coords.extend([(loc["lon"], loc["lat"]) for loc in current_waypoints])
    overview_coords.append((current_lon, current_lat))

    detailed_coords = get_detailed_coords(
        current_waypoints, last_location, steps_data, start_dist
    )
    return old_coords, location_coordinates, overview_coords, detailed_coords


def map_legend(gargling_coords: t.List[dict], gargling_info) -> Image.Image:
    def trim(im):
        bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, 2.0, -100)
        bbox = diff.getbbox()
        if bbox:
            left, upper, right, lower = bbox
            return im.crop((left, upper - 5, right + 5, lower + 5))

    padding = 5
    line_height = 20
    img = Image.new("RGB", (1000, 1000), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("Pillow/Tests/fonts/DejaVuSans.ttf", line_height)
    for i, gargling in enumerate(gargling_coords):
        current_line_height = (line_height + padding) * (i + 1)
        color = gargling_info[gargling["gargling_id"]]["color_hex"]
        name = gargling_info[gargling["gargling_id"]]["first_name"]
        draw.text(
            xy=(0, current_line_height), text="—", fill=color, font=font,
        )
        draw.text(
            xy=(25, current_line_height), text=name, fill="black", font=font,
        )
    trimmed = trim(img)
    return trimmed


def render_map(map_: StaticMap, retry=True) -> t.Optional[Image.Image]:
    try:
        img = map_.render()
    except Exception:
        if retry:
            return render_map(map_, retry=False)
        log.error("Error rendering map", exc_info=True)
        img = None
    return img


def merge_maps(
    overview_img: t.Optional[Image.Image],
    detailed_img: t.Optional[Image.Image],
    legend: Image.Image,
) -> t.Optional[bytes]:
    if detailed_img is not None:
        detailed_img.paste(legend, (detailed_img.width - legend.width, 0))

    if overview_img is not None and detailed_img is not None:
        sep = Image.new("RGB", (3, overview_img.height), (255, 255, 255))
        img = Image.new(
            "RGB",
            (
                (overview_img.width + sep.width + detailed_img.width),
                overview_img.height,
            ),
        )
        img.paste(overview_img, (0, 0))
        img.paste(sep, (overview_img.width, 0))
        img.paste(detailed_img, (overview_img.width + sep.width, 0))
    elif overview_img is not None:
        img = overview_img
    elif detailed_img is not None:
        img = detailed_img
    else:
        return None
    bytes_io = BytesIO()
    img.save(bytes_io, format="JPEG")
    return bytes_io.getvalue()


def generate_traversal_map(
    conn: connection,
    journey_id: int,
    last_location: t.Optional[dict],
    current_lat: float,
    current_lon: float,
    current_distance: float,
    steps_data: t.List[dict],
    gargling_info: t.Dict[int, dict],
) -> t.Optional[bytes]:
    old_coords, locations, overview_coords, detailed_coords = traversal_data(
        conn,
        journey_id,
        last_location,
        current_lat,
        current_lon,
        current_distance,
        steps_data,
    )
    template = "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png"
    height = 600
    width = 1000
    overview_map = StaticMap(width=width, height=height, url_template=template)
    if old_coords:
        overview_map.add_line(Line(old_coords, "grey", 2))
    for lon, lat in locations:
        overview_map.add_marker(CircleMarker((lon, lat), "blue", 6))
    overview_map.add_line(Line(overview_coords, "red", 2))
    overview_map.add_marker(CircleMarker((current_lon, current_lat), "red", 6))

    detailed_map = StaticMap(width=width, height=height, url_template=template)
    start = detailed_coords[0]["coords"][0]
    detailed_map.add_marker(CircleMarker(start, "black", 6))
    detailed_map.add_marker(CircleMarker(start, "grey", 4))
    for gargling in detailed_coords:
        color = gargling_info[gargling["gargling_id"]]["color_hex"]
        detailed_map.add_line(Line(gargling["coords"], "grey", 4))
        detailed_map.add_line(Line(gargling["coords"], color, 2))
        detailed_map.add_marker(CircleMarker(gargling["coords"][-1], "black", 6))
        detailed_map.add_marker(CircleMarker(gargling["coords"][-1], color, 4))
    legend = map_legend(detailed_coords, gargling_info)

    overview_img = render_map(overview_map)
    detailed_img = render_map(detailed_map)
    img = merge_maps(overview_img, detailed_img, legend)
    return img


def upload_images(
    journey_id: int,
    waypoint_id: int,
    street_view_img: t.Optional[bytes],
    traversal_map: t.Optional[bytes],
) -> t.Tuple[t.Optional[str], t.Optional[str]]:
    dbx = Dropbox(config.dropbox_token)

    def upload(data: bytes, name: str) -> t.Optional[str]:
        path = config.dbx_journey_folder / f"{journey_id}_{waypoint_id}_{name}.jpg"
        try:
            uploaded = dbx.files_upload(f=data, path=path.as_posix(), autorename=True)
        except Exception:
            log.error("Error uploading streetview image", exc_info=True)
            return None
        shared = dbx.sharing_create_shared_link(uploaded.path_display)
        url = shared.url.replace("?dl=0", "?raw=1")
        return url

    sw_url = upload(street_view_img, name="street_view") if street_view_img else None
    traversal_map_url = upload(traversal_map, name="map") if traversal_map else None
    return sw_url, traversal_map_url


def most_recent_location(conn, journey_id) -> t.Optional[dict]:
    loc = queries.most_recent_location(conn, journey_id=journey_id)
    if loc is None:
        return None
    loc = dict(loc)
    loc["date"] = pendulum.Date(loc["date"].year, loc["date"].month, loc["date"].day)
    return loc


def perform_daily_update(
    conn: connection,
    journey_id: int,
    date: pendulum.Date,
    steps_data: t.List[dict],
    gargling_info: t.Dict[int, dict],
):
    journey = queries.get_journey(conn, journey_id=journey_id)
    if journey["finished_at"] is not None or journey["started_at"] is None:
        return None
    steps_data.sort(key=itemgetter("amount"), reverse=True)
    steps_today = sum(data["amount"] for data in steps_data)
    if steps_today == 0:
        return None

    last_location = most_recent_location(conn, journey_id)
    last_total_distance = last_location["distance"] if last_location else 0

    distance_today = steps_today * stride
    distance_total = distance_today + last_total_distance
    dist_remaining = journey["distance"] - distance_total
    lat, lon, latest_waypoint_id, finished = get_location(
        conn, journey_id, distance_total
    )
    address, street_view_img, map_url, poi = data_for_location(lat, lon)

    traversal_map = generate_traversal_map(
        conn,
        journey_id,
        last_location,
        lat,
        lon,
        distance_total,
        steps_data,
        gargling_info,
    )
    img_url, traversal_map_url = upload_images(
        journey_id, latest_waypoint_id, street_view_img, traversal_map,
    )
    location = {
        "journey_id": journey_id,
        "latest_waypoint": latest_waypoint_id,
        "lat": lat,
        "lon": lon,
        "distance": distance_total,
        "date": date,
        "address": address,
        "img_url": img_url,
        "map_url": map_url,
        "traversal_map_url": traversal_map_url,
        "poi": poi,
    }
    return location, distance_today, dist_remaining, finished


def days_to_update(conn, journey_id, date: pendulum.Date) -> t.Iterable[pendulum.Date]:
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


def round_meters(n: float) -> str:
    if n < 1000:
        unit = "m"
    else:
        n /= 1000
        unit = "km"
    n = round(n, 1)
    if int(n) == n:
        n = int(n)
    return f"{n} {unit}"


def format_response(
    destination: str,
    n_day: int,
    date: pendulum.Date,
    steps_data: list,
    dist_today: float,
    distance: float,
    dist_remaining: float,
    address: t.Optional[str],
    poi: t.Optional[str],
    img_url: t.Optional[str],
    map_url: str,
    traversal_map_url: t.Optional[str],
    body_reports: t.Optional[t.List[str]],
    finished: bool,
    gargling_info: t.Dict[int, dict],
) -> dict:
    blocks = []
    title_txt = (
        f"*Ekspedisjonsrapport {date.day}.{date.month}.{date.year} - dag {n_day}*"
        if not finished
        else "*Ekspedisjon complete!*"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": title_txt}})

    distance_summary = f"Vi gikk *{round_meters(dist_today)}*!"
    distance_txt = distance_summary + (
        f" Nå har vi gått {round_meters(distance)} totalt på vår journey til {destination} -"
        f" vi har {round_meters(dist_remaining)} igjen til vi er framme."
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": distance_txt}})

    steps_txt = "Steps taken:"
    for i, row in enumerate(steps_data):
        color = gargling_info[row["gargling_id"]]["color_name"]
        name = gargling_info[row["gargling_id"]]["first_name"]

        steps = row["amount"]
        g_distance = round_meters(steps * stride)
        if i == 0:
            amount = f"*{steps}* ({g_distance}) :star:"
        elif i == len(steps_data) - 1:
            amount = f"_{steps}_ ({g_distance})"
        else:
            amount = f"{steps} ({g_distance})"
        desc = f"\n\t:dot-{color}: {name}: {amount}"
        steps_txt += desc
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": steps_txt}})

    if traversal_map_url is not None:
        blocks.append(
            {"type": "image", "image_url": traversal_map_url, "alt_text": "Breakdown!"}
        )

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

    if body_reports:
        blocks.append({"type": "divider"})
        body_txt = "Also: " + "".join(body_reports)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body_txt}})

    response = {"text": f"{title_txt}: {distance_summary}", "blocks": blocks}
    return response


def store_update_data(conn, location_data, finished):
    queries.add_location(conn, **location_data)
    if finished:
        queries.finish_journey(
            conn, journey_id=location_data["journey_id"], date=location_data["date"]
        )


def store_steps(conn, steps, journey_id, date) -> None:
    for step in steps:
        step["taken_at"] = date
        step["journey_id"] = journey_id
    queries.add_steps(conn, steps)


def main(conn: connection, current_date: pendulum.Date) -> t.Iterator[dict]:
    ongoing_journey = queries.get_ongoing_journey(conn)
    journey_id = ongoing_journey["id"]
    destination = ongoing_journey["destination"]
    try:
        for date in days_to_update(conn, journey_id, current_date):
            log.info(f"Journey update for {date}")
            with conn:
                activity_data = health.activity(conn, date)
                if not activity_data:
                    continue
                steps_data, body_reports = activity_data
            gargling_info = get_colors_names(
                conn, ids=[gargling["gargling_id"] for gargling in steps_data]
            )
            update_data = perform_daily_update(
                conn=conn,
                journey_id=journey_id,
                date=date,
                steps_data=steps_data,
                gargling_info=gargling_info,
            )
            if not update_data:
                continue
            location, distance_today, dist_remaining, finished = update_data
            n_day = (date - ongoing_journey["started_at"]).days + 1
            formatted = format_response(
                date=date,
                destination=destination,
                n_day=n_day,
                steps_data=steps_data,
                body_reports=body_reports,
                dist_today=distance_today,
                dist_remaining=dist_remaining,
                finished=finished,
                gargling_info=gargling_info,
                distance=location["distance"],
                address=location["address"],
                poi=location["poi"],
                img_url=location["img_url"],
                map_url=location["map_url"],
                traversal_map_url=location["traversal_map_url"],
            )
            yield formatted
            with conn:
                store_update_data(conn, location, finished)
                store_steps(conn, steps_data, journey_id, date)

    except Exception as exc:
        log.exception(exc)
        return []
