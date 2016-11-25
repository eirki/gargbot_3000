#! /usr/bin/env python3.5
# coding: utf-8
from __future__ import unicode_literals, print_function

import random
import json
import os
import asyncio

import dropbox
from PIL import Image

import config


class DropPics(object):
    def connect(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        print("Connected to dbx")

    def get_pic(self, topic=None):
        topics = {
            "lark": self.lark_paths,
            "fe": self.fe_paths,
            "skating": self.skate_paths,
        }
        if topic is None:
            topic = random.choice(list(topics.keys()))
        path = random.choice(topics[topic])
        response = self.dbx.sharing_create_shared_link(path)
        return response.url.replace("?dl=0", "?raw=1")

    def load_img_paths(self):
        with open(os.path.join(os.getcwd(), "data", "lark_paths.json")) as j:
            self.lark_paths = json.load(j)
        with open(os.path.join(os.getcwd(), "data", "fe_paths.json")) as j:
            self.fe_paths = json.load(j)
        with open(os.path.join(os.getcwd(), "data", "skate_paths.json")) as j:
            self.skate_paths = json.load(j)
        print("Pictures indexed")

    def db_file_path_generator(self, path):
        query = self.dbx.files_list_folder(path, recursive=True)
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
            with open(os.path.join(os.getcwd(), "data", "%s_paths.json" % filename), "w") as j:
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
    return exif[40094].decode('utf-16').rstrip('\x00')

if __name__ == "__main__":
    drop_pics = DropPics()
    drop_pics.connect()
    # drop_pics.store_relevant_img_paths()
    drop_pics.load_img_paths()
    print(drop_pics.get_pic("lark"))
    print(drop_pics.get_pic("fe"))
    print(drop_pics.get_pic("skating"))
    print(drop_pics.get_pic())
