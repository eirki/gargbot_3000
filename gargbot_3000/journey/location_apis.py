#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import base64
from collections.abc import Iterator
import hashlib
import hmac
import typing as t
import urllib.parse

from geopy.geocoders import Nominatim
import googlemaps
import requests

from gargbot_3000 import config
from gargbot_3000.logger import log

poi_radius = 2500

poi_types = {
    "amusement_park",
    "aquarium",
    "art_gallery",
    "bar",
    "beauty_salon",
    "bowling_alley",
    "campground",
    "casino",
    "courthouse",
    "embassy",
    "funeral_home",
    "gym",
    "hair_care",
    "hardware_store",
    "hindu_temple",
    "library",
    "liquor_store",
    "movie_theater",
    "museum",
    "night_club",
    "pet_store",
    "rv_park",
    "spa",
    "stadium",
    "tourist_attraction",
    "zoo",
}


def address_for_location(
    lat, lon
) -> tuple[t.Optional[str], t.Optional[str]]:  # no test coverage
    geolocator = Nominatim(user_agent=config.bot_name)
    try:
        location = geolocator.reverse(f"{lat}, {lon}", language="en")
        address = location.address
        country = location.raw.get("address", {}).get("country")
        return address, country
    except Exception:
        log.error("Error getting address for location", exc_info=True)
        return None, None


def street_view_for_location(lat, lon) -> t.Optional[bytes]:  # no test coverage
    def encode_url(domain, endpoint, params):
        params = params.copy()
        url_to_sign = endpoint + urllib.parse.urlencode(params)
        secret = config.google_api_secret
        decoded_key = base64.urlsafe_b64decode(secret)
        signature = hmac.new(decoded_key, url_to_sign.encode(), hashlib.sha1)
        encoded_signature = base64.urlsafe_b64encode(signature.digest())
        params["signature"] = encoded_signature.decode()
        encoded_url = domain + endpoint + urllib.parse.urlencode(params)
        return encoded_url

    domain = "https://maps.googleapis.com"
    metadata_endpoint = "/maps/api/streetview/metadata?"
    img_endpoint = "/maps/api/streetview?"
    params = {
        "size": "600x400",
        "location": f"{lat}, {lon}",
        "fov": 120,
        "heading": 251.74,
        "pitch": 0,
        "key": config.google_api_key,
    }
    metadata_url = encode_url(domain, metadata_endpoint, params)
    try:
        response = requests.get(metadata_url)
        metadata = response.json()
        if metadata["status"] != "OK":
            log.info(f"Metadata indicates no streetview image: {metadata}")
            return None
    except Exception:
        log.error("Error downloading streetview image metadata", exc_info=True)
        return None

    photo_url = encode_url(domain, img_endpoint, params)
    try:
        response = requests.get(photo_url)
        data = response.content
    except Exception:
        log.error("Error downloading streetview image", exc_info=True)
        return None
    return data


def map_url_for_location(lat, lon) -> str:  # no test coverage
    base = "https://www.google.com/maps/search/?"
    params = {"api": 1, "query": f"{lat},{lon}"}
    url = base + urllib.parse.urlencode(params)
    return url


def poi_for_location(
    lat, lon
) -> tuple[t.Optional[str], t.Optional[bytes]]:  # no test coverage
    try:
        gmaps = googlemaps.Client(key=config.google_api_key)
        places = gmaps.places_nearby(location=(lat, lon), radius=poi_radius)["results"]
    except Exception:
        log.error("Error getting location data", exc_info=True)
        return None, None
    place = next(
        (p for p in places if not poi_types.isdisjoint(p.get("types", []))), None
    )
    if not place:
        log.info("No interesting point of interest")
        return None, None
    name = place["name"]
    try:
        photo_data = next(p for p in place["photos"] if p["width"] >= 1000)
        ref = photo_data["photo_reference"]
        photo_itr = gmaps.places_photo(ref, max_width=2000)
        photo = b"".join([chunk for chunk in photo_itr if chunk])
    except StopIteration:
        log.info("No poi photo big enough")
        return name, None
    except Exception:
        log.error("Error getting poi photo", exc_info=True)
        return name, None
    return name, photo


def main(
    lat_lons: Iterator[tuple[float, float]]
) -> tuple[
    t.Optional[str], t.Optional[str], t.Optional[bytes], str, t.Optional[str],
]:  # no test coverage
    address, sw_photo, map_url, poi, map_url = [None] * 5
    for lat, lon in lat_lons:
        if address is None:
            address, country = address_for_location(lat, lon)
        if poi is None:
            poi, poi_photo = poi_for_location(lat, lon)
        if sw_photo is None:
            sw_photo = street_view_for_location(lat, lon)
        if map_url is None:
            map_url = map_url_for_location(lat, lon)
        if (
            address is not None
            and poi is not None
            and (poi_photo is not None or sw_photo is not None)
        ):
            break
    assert map_url is not None  # satisfy mypy
    photo = poi_photo if poi is not None else sw_photo
    return address, country, photo, map_url, poi
