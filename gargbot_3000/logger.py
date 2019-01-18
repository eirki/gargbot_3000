#! /usr/bin/env python3.6
# coding: utf-8

# Core
import os
import logging
from logging.handlers import SysLogHandler
from logging import StreamHandler
import socket

import typing as t


class ContextFilter(logging.Filter):
    hostname = socket.gethostname()

    def filter(self, record):
        record.hostname = ContextFilter.hostname
        return True


log = logging.getLogger()
formatter = logging.Formatter("%(filename)s %(levelname)s - %(message)s")

handler: t.Union[SysLogHandler, StreamHandler]
try:
    log_address = (os.environ["loghost"], int(os.environ["logport"]))
    handler = SysLogHandler(address=log_address)
    handler.addFilter(ContextFilter())
except KeyError:
    handler = StreamHandler()

handler.setFormatter(formatter)
log.addHandler(handler)
log.setLevel(os.environ.get("loglevel", "INFO"))
