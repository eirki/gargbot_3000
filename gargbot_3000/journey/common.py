#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import aiosql
import gpxpy
from psycopg2.extensions import connection

STRIDE = 0.75
queries = aiosql.from_path("sql/journey", "psycopg2")


def location_between_waypoints(
    first_waypoint, last_waypoint, distance: float
) -> tuple[float, float]:
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


def get_colors_names(conn: connection, ids: list[int]) -> dict[int, dict]:
    infos = queries.journey.colors_names_for_ids(conn, ids=ids)
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
    for info in infos:  # no test coverage
        gargling_id = info["id"]
        del info["id"]
        infodict[gargling_id] = dict(info)
