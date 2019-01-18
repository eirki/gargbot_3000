#! /usr/bin/env python3.6
# coding: utf-8

# Core
import sys

# Internal
from gargbot_3000 import config
from gargbot_3000 import task
from gargbot_3000 import server

app = server.app


def start_task():
    task.main()


def start_server():
    server.main()


if __name__ == "__main__":
    if sys.argv[1] == "task":
        start_task()

    elif sys.argv[1] == "server":
        start_server()
