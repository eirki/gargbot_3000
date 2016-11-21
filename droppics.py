#! /usr/bin/env python
# coding: utf-8
from __future__ import unicode_literals, print_function

import random
import json
import os

import dropbox

import config


class DropPics(object):
    def connect(self):
        self.dbx = dropbox.Dropbox(config.dropbox_token)
        self.dbx.users_get_current_account()
        print("Connected to dbx")

    def get_lark(self):
        path = random.choice(self.lark_paths)
        response = self.dbx.sharing_create_shared_link(path)
        return response.url.replace("?dl=0", "?raw=1")

    def load_lark_paths(self):
        with open(os.path.join(os.getcwd(), "data", "lark_paths.json")) as j:
            self.lark_paths = json.load(j)
        print("Lark pictures indexed")

    def store_lark_paths(self):
        paths = []
        for folder in config.lark_folders:
            for img in self.dbx.files_list_folder(folder).entries:
                paths.append(img.path_lower)

        with open(os.path.join(os.getcwd(), "data", "lark_paths.json"), "w") as j:
            json.dump(paths, j)


if __name__ == "__main__":
    drop_pics = DropPics()
    drop_pics.connect()
    # drop_pics.store_lark_paths()
    drop_pics.load_lark_paths()
    print(drop_pics.get_lark())
