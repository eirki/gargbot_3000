#! /usr/bin/env python3
# coding: utf-8
from operator import itemgetter
import typing as t

from dropbox import Dropbox
import gpxpy
import pendulum
from psycopg2.extensions import connection
from slackclient import SlackClient

from gargbot_3000 import config, database, health, task
from gargbot_3000.journey import achievements, common, location_apis, mapping
from gargbot_3000.journey.common import STRIDE, queries
from gargbot_3000.logger import log


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
            "distance": cumulative_distance,
        }
        waypoints.append(data)
        prev_waypoint = waypoint
    queries.add_waypoints(conn, waypoints)


def coordinates_for_distance(
    conn, journey_id, distance
) -> t.Tuple[float, float, int, bool]:
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
        remaining_dist = distance - latest_waypoint["distance"]
        current_lat, current_lon = common.location_between_waypoints(
            latest_waypoint, next_waypoint, remaining_dist
        )
    return current_lat, current_lon, latest_waypoint["id"], finished


def upload_images(
    journey_id: int,
    date: pendulum.Date,
    photo: t.Optional[bytes],
    traversal_map: t.Optional[bytes],
) -> t.Tuple[t.Optional[str], t.Optional[str]]:
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


def perform_daily_update(
    conn: connection,
    journey_id: int,
    date: pendulum.Date,
    steps_data: t.List[dict],
    gargling_info: t.Dict[int, dict],
) -> t.Optional[
    t.Tuple[dict, float, float, t.Optional[str], str, t.Optional[str], bool, bool]
]:
    journey = queries.get_journey(conn, journey_id=journey_id)
    if journey["finished_at"] is not None or journey["started_at"] is None:
        return None
    steps_data.sort(key=itemgetter("amount"), reverse=True)
    steps_today = sum(data["amount"] for data in steps_data)
    if steps_today == 0:
        return None

    last_location = most_recent_location(conn, journey_id)
    last_total_distance = last_location["distance"] if last_location else 0

    distance_today = steps_today * STRIDE
    distance_total = distance_today + last_total_distance
    dist_remaining = journey["distance"] - distance_total
    lat, lon, latest_waypoint_id, finished = coordinates_for_distance(
        conn, journey_id, distance_total
    )
    address, country, photo, map_url, poi = location_apis.main(lat, lon)

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
        dist_remaining,
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
    destination: str,
    n_day: int,
    date: pendulum.Date,
    steps_data: list,
    dist_today: float,
    distance: float,
    dist_remaining: float,
    address: t.Optional[str],
    country: t.Optional[str],
    poi: t.Optional[str],
    photo_url: t.Optional[str],
    map_url: str,
    map_img_url: t.Optional[str],
    body_reports: t.Optional[t.List[str]],
    finished: bool,
    gargling_info: t.Dict[int, dict],
    achievement: t.Optional[str],
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
        g_distance = round_meters(steps * STRIDE)
        if i == 0:
            amount = f"*{steps}* ({g_distance}) :star:"
        elif i == len(steps_data) - 1:
            amount = f"_{steps}_ ({g_distance})"
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
        location_txt += f"Kveldens underholdning er {poi}."
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
                "text": f"<{map_url}|Ta en kikk på kartet da vel!>",
            },
        }
    )

    if body_reports:
        blocks.append({"type": "divider"})
        body_txt = "Also: " + "".join(body_reports)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": body_txt}})

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
    destination = ongoing_journey["destination"]
    try:
        for date in days_to_update(conn, journey_id, current_date):
            log.info(f"Journey update for {date}")
            with conn:
                activity_data = health.activity(conn, date)
                if not activity_data:
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
            if not update_data:
                continue
            (
                location,
                distance_today,
                dist_remaining,
                photo_url,
                map_url,
                map_img_url,
                new_country,
                finished,
            ) = update_data
            store_update_data(conn, location, finished)
            store_steps(conn, steps_data, journey_id, date)
            achievement = achievements.new(conn, journey_id, date, gargling_info)
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
                country=location["country"] if new_country else None,
                poi=location["poi"],
                photo_url=photo_url,
                map_url=map_url,
                map_img_url=map_img_url,
                achievement=achievement,
            )
            yield formatted
            conn.commit()
    except Exception:
        log.error(f"Error in journey.main", exc_info=True)


def run_updates() -> None:
    current_date = pendulum.now()
    try:
        # now() function sometimes returns a date, not datetime??
        current_date.hour
        current_date = current_date.date()
    except AttributeError:
        pass
    conn = database.connect()
    try:
        slack_client = SlackClient(config.slack_bot_user_token)
        for update in main(conn, current_date):
            task.send_response(slack_client, update, channel=config.health_channel)
    finally:
        conn.close()
