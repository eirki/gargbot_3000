#! /usr/bin/env python3
# coding: utf-8
import typing as t

import aiosql
import gpxpy
from psycopg2.extensions import connection

STRIDE = 0.75
queries = aiosql.from_path("sql/journey.sql", "psycopg2")


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
