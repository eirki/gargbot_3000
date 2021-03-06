#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".") / ".env.local")
load_dotenv(dotenv_path=Path(".") / ".env")

server_name = os.environ.get("SERVER_NAME")

slack_verification_token = os.environ["slack_verification_token"]
slack_bot_user_token = os.environ["slack_bot_user_token"]
slack_oauth_access_token = os.environ["slack_oauth_access_token"]
slack_client_id = os.environ["slack_client_id"]
slack_client_secret = os.environ["slack_client_secret"]
slack_signing_secret = os.environ["slack_signing_secret"]
slack_team_id = os.environ["slack_team_id"]
slack_redirect_url = os.environ["slack_redirect_url"]

app_secret = os.environ["app_secret"]

bot_id = os.environ["bot_id"]
bot_name = os.environ["bot_name"]

home = Path(os.getenv("home_folder", os.getcwd()))

db_name = os.environ["POSTGRES_DB"]
db_user = os.environ["POSTGRES_USER"]
db_password = os.environ["POSTGRES_PASSWORD"]
db_host = os.environ["POSTGRES_HOST"]
db_port = os.environ["POSTGRES_PORT"]
db_uri = f"postgres://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

dropbox_token = os.environ["dropbox_token"]

dbx_pic_folder = os.environ["dbx_pic_folder"]
dbx_journey_folder = Path(os.environ["dbx_journey_folder"])
dbx_db_backup_folder = Path(os.environ["dbx_db_backup_folder"])
tz = os.environ["tz"]

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

polar_client_id = os.environ["polar_client_id"]
polar_client_secret = os.environ["polar_client_secret"]
polar_redirect_uri = os.environ["polar_redirect_uri"]

googlefit_client_id = os.environ["googlefit_client_id"]
googlefit_client_secret = os.environ["googlefit_client_secret"]
googlefit_redirect_uri = os.environ["googlefit_redirect_uri"]
googlefit_javascript_origins = os.environ["googlefit_javascript_origins"]
googlefit_auth_uri = os.environ["googlefit_auth_uri"]
googlefit_token_uri = os.environ["googlefit_token_uri"]
googlefit_auth_provider_x509_cert_url = os.environ[
    "googlefit_auth_provider_x509_cert_url"
]

google_api_key = os.environ["google_api_key"]
google_api_secret = os.environ["google_api_secret"]
