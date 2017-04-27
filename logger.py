import logging
import os
import datetime as dt

log = logging.getLogger()
log.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

log_path = os.path.join("/home", "eirki", "gargbot_3000", "logs", "gargbot")
if os.path.exists(log_path + ".log"):
    os.rename(log_path + ".log", f"{log_path}{str(dt.datetime.now().replace(microsecond=0))}.log")

fh = logging.FileHandler(f"{log_path}.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
log.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
log.addHandler(ch)
