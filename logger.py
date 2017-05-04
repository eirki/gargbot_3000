#! /usr/bin/env python3.6
# coding: utf-8
import logging
import os
import datetime as dt

import config

log = logging.getLogger()
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

log_path = os.path.join(config.home, "logs", "gargbot")
if os.path.exists(log_path + ".log"):
    now = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.rename(log_path + ".log", f"{log_path}{now}.log")

fh = logging.FileHandler(f"{log_path}.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
log.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)
