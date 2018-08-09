#! /usr/bin/env python3.6
# coding: utf-8

# Core
import logging
from pathlib import Path
import os
import datetime as dt

# Internal
from gargbot_3000 import config

log = logging.getLogger()
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
log_path = Path(config.home / "logs" / "gargbot.log")

if log_path.exists():
    now = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(log_path, log_path.with_name(f"gargbot{now}.log"))

try:
    fh = logging.FileHandler(str(log_path))
except FileNotFoundError:
    log_path.parent.mkdir()
    fh = logging.FileHandler(str(log_path))

fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
log.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)
