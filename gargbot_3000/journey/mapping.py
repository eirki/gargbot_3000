#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

from io import BytesIO
import itertools
from operator import itemgetter
from pathlib import Path
import typing as t

from PIL import Image, ImageChops, ImageDraw, ImageFont
from psycopg2.extensions import connection
from staticmap import CircleMarker, Line, StaticMap

from gargbot_3000.journey import common
from gargbot_3000.logger import log

queries = common.queries.journey


def prepare_map_generation(conn, journey_id):
    all_steps = queries.get_steps(conn, journey_id=journey_id)
    all_steps.sort(key=itemgetter("taken_at"))
    steps_for_date = {
        date: list(steps)
        for date, steps in itertools.groupby(all_steps, lambda step: step["taken_at"])
    }
    locations = queries.locations_for_journey(conn, journey_id=journey_id)
    return steps_for_date, locations


def map_for_locs(conn, journey_id, location, last_location, steps_for_date):
    steps_data = steps_for_date[location["date"]]
    steps_data.sort(key=itemgetter("amount"), reverse=True)
    gargling_info = common.get_colors_names(
        conn, ids=[gargling["gargling_id"] for gargling in steps_data]
    )
    img = main(
        conn=conn,
        journey_id=journey_id,
        last_location=last_location,
        current_lat=location["lat"],
        current_lon=location["lon"],
        current_distance=location["distance"],
        steps_data=steps_data,
        gargling_info=gargling_info,
    )
    return img


def generate_map(conn, journey_id, index: int, write=True):  # no test coverage
    steps_for_date, locations = prepare_map_generation(conn, journey_id)
    location = locations[index]
    last_location = locations[index - 1]
    img = map_for_locs(conn, journey_id, location, last_location, steps_for_date)
    if write is False:
        return img
    elif img is not None:
        with open(
            (Path.cwd() / location["date"].isoformat()).with_suffix((".jpg")), "wb"
        ) as f:
            f.write(img)


def generate_all_maps(conn, journey_id, write=True):
    steps_for_date, locations = prepare_map_generation(conn, journey_id)
    last_location = None
    imgs = []
    for location in locations:
        img = map_for_locs(conn, journey_id, location, last_location, steps_for_date)
        if write is False:
            imgs.append(img)
        elif img is not None:  # no test coverage
            with open(
                (Path.cwd() / location["date"].isoformat()).with_suffix((".jpg")), "wb"
            ) as f:
                f.write(img)
        last_location = location


def get_detailed_coords(current_waypoints, last_location, steps_data, start_dist):
    detailed_coords: list[dict] = []
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
        gargling_distance = gargling["amount"] * common.STRIDE
        current_distance += gargling_distance
        while True:
            if next_waypoint is None or next_waypoint["distance"] < current_distance:
                # next_waypoint from previous garglings has been passed
                next_waypoint = next(waypoints_itr, None)
                if next_waypoint is None:  # no test coverage
                    # this shouldn't really happen
                    break

            if next_waypoint["distance"] < current_distance:
                # next_waypoint passed by this gargling
                gargling_coords.append((next_waypoint["lon"], next_waypoint["lat"]))
                latest_waypoint = next_waypoint
                continue
            elif next_waypoint["distance"] >= current_distance:
                # next_waypoint will not be passed by this gargling
                remaining_dist = current_distance - latest_waypoint["distance"]
                last_lat, last_lon = common.location_between_waypoints(
                    latest_waypoint, next_waypoint, remaining_dist
                )
                gargling_coords.append((last_lon, last_lat))
                # assign starting location for next gargling
                latest_waypoint = {
                    "lat": last_lat,
                    "lon": last_lon,
                    "distance": current_distance,
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
    steps_data: list[dict],
) -> t.Tuple[
    list[t.Tuple[float, float]],
    list[t.Tuple[float, float]],
    list[t.Tuple[float, float]],
    list[dict],
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
        {"lat": current_lat, "lon": current_lon, "distance": current_distance}
    )
    overview_coords.extend([(loc["lon"], loc["lat"]) for loc in current_waypoints])
    overview_coords.append((current_lon, current_lat))

    detailed_coords = get_detailed_coords(
        current_waypoints, last_location, steps_data, start_dist
    )
    return old_coords, location_coordinates, overview_coords, detailed_coords


def map_legend(gargling_coords: list[dict], gargling_info) -> Image.Image:
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


def render_map(
    map_: StaticMap, retry=True
) -> t.Optional[Image.Image]:  # no test coverage
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
    elif overview_img is not None:  # no test coverage
        img = overview_img
    elif detailed_img is not None:  # no test coverage
        img = detailed_img
    else:  # no test coverage
        return None
    bytes_io = BytesIO()
    img.save(bytes_io, format="JPEG", subsampling=0, quality=100)
    return bytes_io.getvalue()


def main(
    conn: connection,
    journey_id: int,
    last_location: t.Optional[dict],
    current_lat: float,
    current_lon: float,
    current_distance: float,
    steps_data: list[dict],
    gargling_info: dict[int, dict],
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
