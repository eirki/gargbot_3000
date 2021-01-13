#! /usr/bin/env python3
# coding: utf-8
from functools import partial

import aiosql
from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import geojson
import pendulum

from gargbot_3000.journey import journey
from gargbot_3000.journey.common import queries

blueprint = Blueprint("journey", __name__)
user_queries = aiosql.from_path("sql/gargling.sql", "psycopg2")


@blueprint.route("/detail_journey/<journey_id>")
def detail_journey(journey_id):
    with current_app.pool.get_connection() as conn:
        j = queries.journey.get_journey(conn, journey_id=journey_id)
        most_recent = journey.most_recent_location(conn, journey_id)
        if most_recent is None:
            return jsonify(waypoints=[])

        waypoints = queries.journey.waypoints_between_distances(
            conn, journey_id=journey_id, low=0, high=most_recent["distance"]
        )
        waypoints = [
            [point["lon"], point["lat"], point["elevation"]] for point in waypoints
        ]
        waypoints.append([most_recent["lon"], most_recent["lat"], waypoints[-1][-1]])
        as_geojson = geojson.LineString(waypoints)
        locations = queries.journey.locations_for_journey(conn, journey_id=journey_id)
        locations = [dict(point) for point in locations]
    return jsonify(waypoints=as_geojson, locations=locations, **dict(j))


@blueprint.route("/list_journeys")
@jwt_required
def list_journeys():
    with current_app.pool.get_connection() as conn:
        journeys = queries.journey.all_journeys(conn)
        journeys = [dict(j) for j in journeys]
    return jsonify(journeys=journeys)


@blueprint.route("/upload_journey", methods=["POST"])
@jwt_required
def handle_journey_upload():
    gargling_id = get_jwt_identity()
    with current_app.pool.get_connection() as conn:
        if not user_queries.is_admin(conn, gargling_id=gargling_id):
            return Response(status=403)
    origin = request.form["origin"]
    dest = request.form["dest"]
    xmlfile = request.files["file"]
    with current_app.pool.get_connection() as conn:
        journey_id = journey.define_journey(conn, origin, dest)
        journey.parse_gpx(conn, journey_id, xmlfile)
        conn.commit()
    return Response(status=200)


@blueprint.route("/start_journey")
@jwt_required
def start_journey():
    gargling_id = get_jwt_identity()
    with current_app.pool.get_connection() as conn:
        if not user_queries.is_admin(conn, gargling_id=gargling_id):
            return Response(status=403)
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        date = pendulum.now()
        queries.journey.start_journey(conn, journey_id=journey_id, date=date)
        conn.commit()
    return Response(status=200)


@blueprint.route("/stop_journey")
@jwt_required
def stop_journey():
    gargling_id = get_jwt_identity()
    with current_app.pool.get_connection() as conn:
        if not user_queries.is_admin(conn, gargling_id=gargling_id):
            return Response(status=403)
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        queries.journey.stop_journey(conn, journey_id=journey_id)
        conn.commit()
    return Response(status=200)


@blueprint.route("/delete_journey")
@jwt_required
def delete_journey():
    gargling_id = get_jwt_identity()
    with current_app.pool.get_connection() as conn:
        if not user_queries.is_admin(conn, gargling_id=gargling_id):
            return Response(status=403)
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        queries.journey.delete_journey(conn, journey_id=journey_id)
        conn.commit()
    return Response(status=200)


@blueprint.route("/run_journey_update")
@jwt_required
def run_journey_update():
    gargling_id = get_jwt_identity()
    with current_app.pool.get_connection() as conn:
        if not user_queries.is_admin(conn, gargling_id=gargling_id):
            return Response(status=403)
    try:
        journey.run_updates()
    except Exception:
        return Response(status=500)
    else:
        return Response(status=200)


@blueprint.route("/dashboard/<chart_name>/<journey_id>")
@jwt_required
def dashboard(chart_name, journey_id):
    gargling_id = get_jwt_identity()
    print("ID", gargling_id)
    funcs = {
        "distance_area": partial(
            queries.dashboard.distance_area, gargling_id=gargling_id
        ),
        "personal_stats": queries.dashboard.personal_stats,
        "steps_pie": queries.dashboard.steps_pie,
        "first_place_pie": queries.dashboard.first_place_pie,
        "above_median_pie": queries.dashboard.above_median_pie,
        "contributing_days_pie": queries.dashboard.contributing_days_pie,
        "weekday_polar": queries.dashboard.weekday_polar,
        "month_polar": queries.dashboard.month_polar,
        "countries_timeline": queries.dashboard.countries_timeline,
    }
    func = funcs[chart_name]
    with current_app.pool.get_connection() as conn:
        data = func(conn, journey_id=journey_id)
    response = {}
    if chart_name == "personal_stats":
        gargling_name = next(
            datum["name"] for datum in data if datum["gargling_id"] == gargling_id
        )
        response["name"] = gargling_name
    data = [dict(datum) for datum in data]
    response["data"] = data
    return response
