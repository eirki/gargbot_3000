#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
import json
from os import path
import asyncio
import time

import dropbox
from PIL import Image

import config


class DropPics:
    def connect(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        log.info("Connected to dbx")

    def get_pic(self, topic=None):
        topics = {
            "lark": self.lark_paths,
            "fe": self.fe_paths,
            "skating": self.skate_paths,
            "henging": self.henging_paths,
            "spillnight": self.spill_paths
        }
        if topic is None:
            topic = random.choice(list(topics.keys()))
        file_path = random.choice(topics[topic])

        md = self.dbx.files_get_metadata(file_path, include_media_info=True)
        date_obj = md.media_info.get_metadata().time_taken
        timestamp = int(time.mktime(date_obj.timetuple()))

        response = self.dbx.sharing_create_shared_link(file_path)
        url = response.url.replace("?dl=0", "?raw=1")
        return url, timestamp

    def load_img_paths(self):
        with open(path.join(config.home, "data", "lark_paths.json")) as j:
            self.lark_paths = json.load(j)
        with open(path.join(config.home, "data", "fe_paths.json")) as j:
            self.fe_paths = json.load(j)
        with open(path.join(config.home, "data", "skate_paths.json")) as j:
            self.skate_paths = json.load(j)
        with open(path.join(config.home, "data", "henging_paths.json")) as j:
            self.henging_paths = json.load(j)
        with open(path.join(config.home, "data", "spill_paths.json")) as j:
            self.spill_paths = json.load(j)
        log.info("Pictures indexed")

    def db_file_path_generator(self, dir):
        query = self.dbx.files_list_folder(dir, recursive=True)
        while True:
            for entry in query.entries:
                yield entry
            if not query.has_more:
                break
            query = self.dbx.files_list_folder_continue(query.cursor)

    def store_relevant_img_paths(self):
        self.skate_paths = []
        self.fe_paths = []
        self.lark_paths = []

        loop = asyncio.get_event_loop()
        tasks = [loop.create_task(self.check_relevance(entry, loop))
                 for entry in self.db_file_path_generator(config.kamera_paths)]

        loop.run_until_complete(asyncio.wait(tasks))
        loop.close()

        for filename, data in [("skate", self.skate_paths), ("fe", self.fe_paths), ("lark", self.lark_paths)]:
            with open(path.join(config.home, "data", f"{filename}_paths.json"), "w") as j:
                json.dump(data, j)

    async def check_relevance(self, entry, loop):
        if not entry.path_lower.endswith(".jpg"):
            return
        metadata, response = await loop.run_in_executor(None, self.dbx.files_download, entry.path_lower)
        tag = get_tag(response.raw)
        if not tag:
            return
        elif "Forsterka Enhet" in tag:
            self.fe_paths.append(entry.path_lower)
        elif "Skating" in tag:
            self.skate_paths.append(entry.path_lower)
        elif "Larkollen" in tag:
            self.lark_paths.append(entry.path_lower)


def get_tag(fileobject):
    im = Image.open(fileobject)
    exif = im._getexif()
    return exif[40094].decode("utf-16").rstrip("\x00")


if __name__ == "__main__":
    drop_pics = DropPics()
    drop_pics.connect()
    # drop_pics.store_relevant_img_paths()
    drop_pics.load_img_paths()
    log.info(drop_pics.get_pic("lark"))
    log.info(drop_pics.get_pic("fe"))
    log.info(drop_pics.get_pic("skating"))
    log.info(drop_pics.get_pic())
