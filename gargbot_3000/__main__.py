#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import argparse

from gargbot_3000 import database, scheduler, server
from gargbot_3000.logger import log


def main():  # no test coverage
    try:
        log.info("Starting gargbot_3000")
        parser = argparse.ArgumentParser()
        parser.add_argument("--mode", "-m")
        parser.add_argument("--debug", "-d", action="store_true")
        parser.add_argument("--bind", "-b", default="0.0.0.0")
        parser.add_argument("--workers", "-w", default=3)
        parser.add_argument("--port", "-p", default=":5000")
        args = parser.parse_args()

        if args.mode == "server":
            options = {"bind": "%s%s" % (args.bind, args.port), "workers": args.workers}
            server.main(options=options, debug=args.debug)
        elif args.mode == "scheduler":
            scheduler.main()
        elif args.mode == "migrate":
            database.migrate()
        else:
            raise Exception(f"Incorrect mode, {args.mode}")

    except Exception as exc:
        log.exception(exc)
        raise


if __name__ == "__main__":
    main()
