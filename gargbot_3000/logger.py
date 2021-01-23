#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import logging
from logging import StreamHandler
import os

log = logging.getLogger()
formatter = logging.Formatter("%(filename)s %(levelname)s - %(message)s")

handler = StreamHandler()
handler.setFormatter(formatter)
log.addHandler(handler)
log.setLevel(os.environ.get("loglevel", "INFO"))
