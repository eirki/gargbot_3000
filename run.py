#! /usr/bin/env python3.6
# coding: utf-8

# From https://help.pythonanywhere.com/pages/LongRunningTasks/
import socket
import sys
import time

from gargbot_3000 import config


lock_socket = None  # we want to keep the socket open until the very end of
                    # our script so we use a global variable to avoid going
                    # out of scope and being garbage-collected

def is_lock_free():
    global lock_socket
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        lock_id = config.app_id
        lock_socket.bind(f"\0{lock_id}")
        print(f"Acquired lock {lock_id}")
        return True
    except socket.error:
        # socket already locked, task must already be running
        return False


def aquire_lock():
    print("Trying to aquire lock")
    for _ in range(59):
        if is_lock_free():
            break
        time.sleep(60)
    else:
        print("Failed to acquire lock")
        sys.exit()


if len(sys.argv) >= 3 and sys.argv[2] == "aquire_lock":
    aquire_lock()


if sys.argv[1] == "task":
    from gargbot_3000 import task
    task.main()

elif sys.argv[1] == "server":
    from gargbot_3000 import server
    server.main()
