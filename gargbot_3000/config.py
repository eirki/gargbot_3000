#! /usr/bin/env python3.6
# coding: utf-8
import os
from pathlib import Path

from dotenv import load_dotenv
import pytz

load_dotenv(dotenv_path=Path(".") / ".env.local")
load_dotenv(dotenv_path=Path(".") / ".env")

server_name = os.environ.get("SERVER_NAME")

slack_verification_token = os.environ["slack_verification_token"]
slack_bot_user_token = os.environ["slack_bot_user_token"]
slack_client_id = os.environ["slack_client_id"]
slack_client_secret = os.environ["slack_client_secret"]
slack_team_id = os.environ["slack_team_id"]
slack_redirect_url = os.environ["slack_redirect_url"]

app_secret = os.environ["app_secret"]

bot_id = os.environ["bot_id"]
bot_name = os.environ["bot_name"]

app_version = os.environ.get("app_version", "test")

home = Path(os.getenv("home_folder", os.getcwd()))

db_name = os.environ["POSTGRES_DB"]
db_user = os.environ["POSTGRES_USER"]
db_password = os.environ["POSTGRES_PASSWORD"]
db_host = os.environ["POSTGRES_HOST"]
db_port = os.environ["POSTGRES_PORT"]

dropbox_token = os.environ["dropbox_token"]

dbx_pic_folder = os.environ["dbx_pic_folder"]
dbx_journey_folder = Path(os.environ["dbx_journey_folder"])
tz = pytz.timezone(os.environ["tz"])

test_channel = os.environ["test_channel"]
health_channel = os.environ["health_channel"]
main_channel = os.environ["main_channel"]

countdown_message = os.environ["countdown_message"]
ongoing_message = os.environ["ongoing_message"]
finished_message = os.environ["finished_message"]

forum_url = os.environ["forum_url"]

fitbit_client_id = os.environ["fitbit_client_id"]
fitbit_client_secret = os.environ["fitbit_client_secret"]
fitbit_redirect_uri = os.environ["fitbit_redirect_uri"]

withings_client_id = os.environ["withings_client_id"]
withings_consumer_secret = os.environ["withings_consumer_secret"]
withings_redirect_uri = os.environ["withings_redirect_uri"]

google_api_key = os.environ["google_api_key"]
google_api_secret = os.environ["google_api_secret"]
