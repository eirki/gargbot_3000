#! /usr/bin/env python3.6
# coding: utf-8

import os
import datetime as dt
from pathlib import Path

import pytz
from dotenv import load_dotenv

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

slack_verification_token = os.environ["slack_verification_token"]
slack_bot_user_token = os.environ["slack_bot_user_token"]
bot_id = os.environ["bot_id"]
bot_name = os.environ["bot_name"]

home = Path(os.getenv("home_folder", os.getcwd()))

db_url = os.environ["db_url"]

dropbox_token = os.environ["dropbox_token"]

dbx_pic_folder = os.environ["dbx_pic_folder"]

tz = pytz.timezone(os.environ["tz"])

test_channel = os.environ["test_channel"]

main_channel = os.environ["main_channel"]

countdown_message = os.environ["countdown_message"]
ongoing_message = os.environ["ongoing_message"]
finished_message = os.environ["finished_message"]

forum_url = os.environ["forum_url"]

countdown_date = dt.datetime.fromtimestamp(int(os.environ["countdown_date"]), tz=tz)

countdown_args = os.environ["countdown_args"].split(", ")
