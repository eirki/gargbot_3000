#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from collections.abc import Iterator
import math
from operator import itemgetter
import typing as t

from dropbox import Dropbox
import gpxpy
import pendulum
from psycopg2.extensions import connection
import slack

from gargbot_3000 import commands, config, database, health
from gargbot_3000.journey import achievements, common, location_apis, mapping
from gargbot_3000.logger import log

queries = common.queries.journey


def define_journey(conn, origin, destination) -> int:
    journey_id = queries.add_journey(conn, origin=origin, destination=destination)
    return journey_id


def parse_gpx(conn, journey_id, xml_data) -> None:
    gpx = gpxpy.parse(xml_data)
    plist = gpx.tracks[0].segments[0].points
    waypoints: list[dict] = []
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
            "elevation": waypoint.elevation,
            "distance": cumulative_distance,
        }
        waypoints.append(data)
        prev_waypoint = waypoint
    queries.add_waypoints(conn, waypoints)


def coordinates_for_distance(
    conn, journey_id, distance
) -> tuple[float, float, int, bool]:
    latest_waypoint = queries.get_waypoint_for_distance(
        conn, journey_id=journey_id, distance=distance
    )
    next_waypoint = queries.get_next_waypoint_for_distance(
        conn, journey_id=journey_id, distance=distance
    )
    if next_waypoint is None:
        finished = True
        current_lat = latest_waypoint["lat"]
        current_lon = latest_waypoint["lon"]
    else:
        finished = False
        remaining_dist = distance - latest_waypoint["distance"]
        current_lat, current_lon = common.location_between_waypoints(
            latest_waypoint, next_waypoint, remaining_dist
        )
    return current_lat, current_lon, latest_waypoint["id"], finished


def daily_factoid(
    date: pendulum.Date,
    conn: connection,
    journey_data: dict,
    distance_today: float,
    distance_total: float,
) -> str:
    dist_remaining = journey_data["distance"] - distance_total
    destination = journey_data["destination"]

    def remaining_distance() -> str:
        return (
            f"Nå har vi gått {round_meters(distance_total)} totalt på vår journey til {destination}. "
            f"Vi har {round_meters(dist_remaining)} igjen til vi er framme."
        )

    def eta_average():
        n_days = (date - journey_data["started_at"]).days + 1
        distance_average = distance_total / n_days
        days_remaining = math.ceil(dist_remaining / distance_average)
        eta = date.add(days=days_remaining)
        return (
            f"Average daglig progress er {round_meters(distance_average)}. "
            f"Holder vi dette tempoet er vi fremme i {destination} {eta.format('DD. MMMM YYYY', locale='nb')}, "
            f"om {days_remaining} dager."
        )

    def eta_today():
        days_remaining = math.ceil(journey_data["distance"] / distance_today)
        eta = journey_data["started_at"].add(days=days_remaining)
        return f"Hadde vi gått den distansen hver dag ville journeyen vart til {eta.format('DD. MMMM YYYY', locale='nb')}."

    def weekly_summary():
        data = queries.weekly_summary(conn, journey_id=journey_data["id"], date=date)
        steps_week = sum(datum["amount"] for datum in data)
        distance_week = steps_week * common.STRIDE
        max_week = sorted(data, key=itemgetter("amount"))[-1]
        max_week_distance = round_meters(max_week["amount"] * common.STRIDE)
        return (
            f"Denne uken har vi gått {round_meters(distance_week)} til sammen. "
            f"Garglingen som gikk lengst var {max_week['first_name']}, med {max_week_distance}!"
        )

    switch = {
        pendulum.SUNDAY: remaining_distance,
        pendulum.MONDAY: eta_average,
        pendulum.TUESDAY: eta_today,
        pendulum.WEDNESDAY: remaining_distance,
        pendulum.THURSDAY: eta_average,
        pendulum.FRIDAY: eta_today,
        pendulum.SATURDAY: weekly_summary,
    }
    func = switch[date.day_of_week]

    result = f"Vi gikk *{round_meters(distance_today)}*! " + func()
    return result


def upload_images(
    journey_id: int,
    date: pendulum.Date,
    photo: t.Optional[bytes],
    traversal_map: t.Optional[bytes],
) -> tuple[t.Optional[str], t.Optional[str]]:  # no test coverage
    dbx = Dropbox(config.dropbox_token)

    def upload(data: bytes, name: str) -> t.Optional[str]:
        path = config.dbx_journey_folder / f"{journey_id}_{date}_{name}.jpg"
        try:
            uploaded = dbx.files_upload(f=data, path=path.as_posix(), autorename=True)
        except Exception:
            log.error(f"Error uploading {name} image", exc_info=True)
            return None
        shared = dbx.sharing_create_shared_link(uploaded.path_display)
        url = shared.url.replace("?dl=0", "?raw=1")
        return url

    photo_url = upload(photo, name="photo") if photo else None
    map_img_url = upload(traversal_map, name="map") if traversal_map else None
    return photo_url, map_img_url


def most_recent_location(conn, journey_id) -> t.Optional[dict]:
    loc = queries.most_recent_location(conn, journey_id=journey_id)
    if loc is None:
        return None
    loc = dict(loc)
    loc["date"] = pendulum.Date(loc["date"].year, loc["date"].month, loc["date"].day)
    return loc


def lat_lon_increments(
    conn: connection, journey_id: int, distance_total: float, last_total_distance: float
) -> Iterator[tuple[float, float]]:
    incr_length = location_apis.poi_radius * 2
    for intermediate_distance in range(
        int(distance_total), int(last_total_distance + incr_length), -incr_length
    ):
        inter_lat, inter_lon, *_ = coordinates_for_distance(
            conn, journey_id, intermediate_distance
        )
        yield inter_lat, inter_lon


def perform_daily_update(
    conn: connection,
    journey_id: int,
    date: pendulum.Date,
    steps_data: list[dict],
    gargling_info: dict[int, dict],
) -> t.Optional[
    tuple[dict, float, dict, t.Optional[str], str, t.Optional[str], bool, bool]
]:
    journey_data = dict(queries.get_journey(conn, journey_id=journey_id))
    if journey_data["finished_at"] is not None or journey_data["started_at"] is None:
        return None
    journey_data["started_at"] = pendulum.Date(
        year=journey_data["started_at"].year,
        month=journey_data["started_at"].month,
        day=journey_data["started_at"].day,
    )  # TODO: return pendulum instance from db
    steps_data.sort(key=itemgetter("amount"), reverse=True)
    steps_today = sum(data["amount"] for data in steps_data)
    if steps_today == 0:  # no test coverage
        return None

    last_location = most_recent_location(conn, journey_id)
    last_total_distance = last_location["distance"] if last_location else 0

    distance_today = steps_today * common.STRIDE
    distance_total = distance_today + last_total_distance
    lat, lon, latest_waypoint_id, finished = coordinates_for_distance(
        conn, journey_id, distance_total
    )

    lat_lons = lat_lon_increments(conn, journey_id, distance_total, last_total_distance)
    address, country, photo, map_url, poi = location_apis.main(lat_lons)

    new_country = (
        country != last_location["country"]
        if last_location and None not in (country, last_location["country"])
        else False
    )

    traversal_map = mapping.main(
        conn,
        journey_id,
        last_location,
        lat,
        lon,
        distance_total,
        steps_data,
        gargling_info,
    )
    photo_url, map_img_url = upload_images(journey_id, date, photo, traversal_map,)
    location = {
        "journey_id": journey_id,
        "latest_waypoint": latest_waypoint_id,
        "lat": lat,
        "lon": lon,
        "distance": distance_total,
        "date": date,
        "address": address,
        "country": country,
        "poi": poi,
    }
    return (
        location,
        distance_today,
        journey_data,
        photo_url,
        map_url,
        map_img_url,
        new_country,
        finished,
    )


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
    n_day: int,
    date: pendulum.Date,
    steps_data: list,
    factoid: str,
    address: t.Optional[str],
    country: t.Optional[str],
    poi: t.Optional[str],
    photo_url: t.Optional[str],
    map_url: str,
    map_img_url: t.Optional[str],
    body_reports: t.Optional[list[str]],
    finished: bool,
    gargling_info: dict[int, dict],
    achievement: t.Optional[str],
) -> dict:
    blocks = []
    title_txt = (
        f"*Ekspedisjonsrapport {date.day}.{date.month}.{date.year} - dag {n_day}*"
        if not finished
        else "*Ekspedisjon complete!*"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": title_txt}})

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": factoid}})

    steps_txt = "Steps taken:"
    most_steps = steps_data[0]["amount"]
    fewest_steps = steps_data[-1]["amount"]
    for i, row in enumerate(steps_data):
        color = gargling_info[row["gargling_id"]]["color_name"]
        name = gargling_info[row["gargling_id"]]["first_name"]

        steps = row["amount"]
        g_distance = round_meters(steps * common.STRIDE)
        if steps == most_steps:
            amount = f"*{steps}* ({g_distance}) :first_place_medal:"
        elif steps == fewest_steps:
            amount = f"_{steps}_ ({g_distance}) :turtle:"
        elif i == 1:
            amount = f"{steps} ({g_distance}) :second_place_medal:"
        elif i == 2:
            amount = f"{steps} ({g_distance}) :third_place_medal:"
        else:
            amount = f"{steps} ({g_distance})"
        desc = f"\n\t:dot-{color}: {name}: {amount}"
        steps_txt += desc
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": steps_txt}})

    if achievement:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": achievement}}
        )

    if map_img_url is not None:
        blocks.append(
            {"type": "image", "image_url": map_img_url, "alt_text": "Breakdown!"}
        )

    location_txt = ""
    if country is not None:
        location_txt += f"Velkommen til {country}! :confetti_ball: "
    if address is not None:
        location_txt += f"Vi har nå kommet til {address}. "
    if poi is not None:
        location_txt += f"Dagens underholdning er {poi}."
    if location_txt:
        blocks.append(
            {"type": "section", "text": {"type": "mrkdwn", "text": location_txt}}
        )

    if photo_url is not None:
        alt_text = address if address is not None else "Check it!"
        blocks.append({"type": "image", "image_url": photo_url, "alt_text": alt_text})

    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"<{map_url}|Gøggle Maps> | "
                    f"<{config.server_name}/map|Gargbot Kart> | "
                    f"<{config.server_name}/dashboard|Stats>"
                ),
            },
        }
    )

    if body_reports:
        blocks.append({"type": "divider"})
        body_txt = "Also: " + "".join(body_reports)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body_txt}})

    distance_summary = factoid.split("!")[0] + "!"
    response = {
        "text": f"{title_txt}: {distance_summary}".replace("*", ""),
        "blocks": blocks,
    }
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
    try:
        for date in days_to_update(conn, journey_id, current_date):
            log.info(f"Journey update for {date}")
            with conn:
                activity_data = health.activity(conn, date)
                if not activity_data:  # no test coverage
                    continue
                steps_data, body_reports = activity_data
            gargling_info = common.get_colors_names(
                conn, ids=[gargling["gargling_id"] for gargling in steps_data]
            )
            update_data = perform_daily_update(
                conn=conn,
                journey_id=journey_id,
                date=date,
                steps_data=steps_data,
                gargling_info=gargling_info,
            )
            if not update_data:  # no test coverage
                continue
            (
                location,
                distance_today,
                journey_data,
                photo_url,
                map_url,
                map_img_url,
                new_country,
                finished,
            ) = update_data
            store_update_data(conn, location, finished)
            store_steps(conn, steps_data, journey_id, date)
            achievement = achievements.new(conn, journey_id, date, gargling_info)
            factoid = daily_factoid(
                date, conn, journey_data, distance_today, location["distance"],
            )
            n_day = (date - ongoing_journey["started_at"]).days + 1
            formatted = format_response(
                date=date,
                n_day=n_day,
                steps_data=steps_data,
                body_reports=body_reports,
                factoid=factoid,
                finished=finished,
                gargling_info=gargling_info,
                address=location["address"],
                country=location["country"] if new_country else None,
                poi=location["poi"],
                photo_url=photo_url,
                map_url=map_url,
                map_img_url=map_img_url,
                achievement=achievement,
            )
            yield formatted
            conn.commit()
    except Exception:  # no test coverage
        log.error(f"Error in journey.main", exc_info=True)


def run_updates() -> None:  # no test coverage
    current_date = pendulum.now()
    try:
        # now() function sometimes returns a date, not datetime??
        current_date.hour
        current_date = current_date.date()
    except AttributeError:
        pass
    conn = database.connect()
    try:
        slack_client = slack.WebClient(config.slack_bot_user_token)
        for update in main(conn, current_date):
            commands.send_response(slack_client, update, channel=config.health_channel)
    finally:
        conn.close()
