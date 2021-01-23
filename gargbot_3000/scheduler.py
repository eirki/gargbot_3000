#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import sys
import time

import pendulum
import schedule

from gargbot_3000 import config, database, greetings
from gargbot_3000.journey import journey
from gargbot_3000.logger import log


def local_hour_at_utc(hour: int) -> str:  # no test coverage
    utc_hour = pendulum.today(config.tz).at(hour).in_timezone("UTC").hour
    formatted = str(utc_hour).zfill(2) + ":00"
    return formatted


def main():  # no test coverage
    log.info("GargBot 3000 scheduler starter")
    try:
        while True:
            schedule.clear()

            hour = local_hour_at_utc(2)
            log.info(f"Scheduling database.backup at {hour}")
            schedule.every().day.at(hour).do(database.backup)

            hour = local_hour_at_utc(7)
            log.info(f"Scheduling send_congrats at {hour}")
            schedule.every().day.at(hour).do(greetings.send_congrats)

            hour = local_hour_at_utc(12)
            log.info(f"Scheduling update_journey at {hour}")
            schedule.every().day.at(hour).do(journey.run_updates)

            now = pendulum.now(config.tz)
            tomorrow = pendulum.tomorrow(config.tz).at(now.hour, now.minute, now.second)
            seconds_until_this_time_tomorrow = (tomorrow - now).seconds
            for _ in range(seconds_until_this_time_tomorrow):
                schedule.run_pending()
                time.sleep(1)
    except KeyboardInterrupt:
        sys.exit()
