#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

from flask import Flask

from gargbot_3000 import config

app = Flask(__name__)

@app.route('/')
def hello_world() -> str:
    return f"{config.app_id}.home"


@app.route('/gargbot_3000')
def gargbot_3000():
    return "gargbot_3000"


def main():
    # app.run() uwsgi does this
    pass


if __name__ == '__main__':
    main()
