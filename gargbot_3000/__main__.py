#! /usr/bin/env python3.6
# coding: utf-8

# Core
import argparse
import os

# Internal
from gargbot_3000 import config
from gargbot_3000.logger import log
from gargbot_3000 import task
from gargbot_3000 import server

# External
from gunicorn.app.base import BaseApplication


class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options if options is not None else {}
        self.application = app
        super(StandaloneApplication, self).__init__()

    def load_config(self):
        for key, value in self.options.items():
            if key in self.cfg.settings and value is not None:
                self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def main():
    try:
        log.info("Starting gargbot_3000")
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", "-m")
        parser.add_argument("--debug", "-d", action="store_true")
        parser.add_argument("--bind", "-b", default="0.0.0.0")
        parser.add_argument("--workers", "-w", default=3)
        parser.add_argument("--port", "-p", default=":5000")
        args = parser.parse_args()

        if args.mode == "task":
            task.main()

        elif args.mode == "server":
            if args.debug is False:
                options = {"bind": "%s%s" % (args.bind, args.port), "workers": args.workers}
                app = StandaloneApplication(server.app, options)
                app.run()
            else:
                # Workaround for a werzeug reloader bug
                # (https://github.com/pallets/flask/issues/1246)
                os.environ["PYTHONPATH"] = os.getcwd()
                server.app.run(debug=True, host=args.bind)

        else:
            raise Exception(f"Incorrect mode, {args.mode}")

    except Exception as exc:
        log.exception(exc)
        raise


if __name__ == "__main__":
    main()
