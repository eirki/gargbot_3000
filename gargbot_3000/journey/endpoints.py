#! /usr/bin/env python3
# coding: utf-8
from functools import partial

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import pendulum

from gargbot_3000.journey import journey
from gargbot_3000.journey.common import dashboard_queries, queries

blueprint = Blueprint("journey", __name__)


@blueprint.route("/detail_journey/<journey_id>")
def detail_journey(journey_id):
    with current_app.pool.get_connection() as conn:
        j = queries.get_journey(conn, journey_id=journey_id)
        most_recent = journey.most_recent_location(conn, journey_id)
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
                "distance": most_recent["distance"],
            }
        )
        locations = queries.locations_for_journey(conn, journey_id=journey_id)
        locations = [dict(point) for point in locations]
    return jsonify(waypoints=waypoints, locations=locations, **dict(j))


@blueprint.route("/list_journeys")
@jwt_required
def list_journeys():
    with current_app.pool.get_connection() as conn:
        journeys = queries.all_journeys(conn)
        journeys = [dict(j) for j in journeys]
    return jsonify(journeys=journeys)


@blueprint.route("/upload_journey", methods=["POST"])
@jwt_required
def handle_journey_upload():
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
def handle_start_journey():
    journey_id = request.args["journey_id"]
    with current_app.pool.get_connection() as conn:
        date = pendulum.now()
        queries.start_journey(conn, journey_id=journey_id, date=date)
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


@blueprint.route("/dashboard/<chart_name>/<journey_id>")
@jwt_required
def dashboard(chart_name, journey_id):
    gargling_id = get_jwt_identity()
    print("ID", gargling_id)
    funcs = {
        "distance_area": partial(
            dashboard_queries.distance_area, gargling_id=gargling_id
        ),
        "personal_stats": dashboard_queries.personal_stats,
        "steps_pie": dashboard_queries.steps_pie,
        "first_place_pie": dashboard_queries.first_place_pie,
        "above_median_pie": dashboard_queries.above_median_pie,
        "contributing_days_pie": dashboard_queries.contributing_days_pie,
    }
    func = funcs[chart_name]
    with current_app.pool.get_connection() as conn:
        data = func(conn, journey_id=journey_id)
    data = [dict(datum) for datum in data]
    return {"data": data}
