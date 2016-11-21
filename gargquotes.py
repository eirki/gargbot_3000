#! /usr/bin/env python
# coding: utf-8
from __future__ import unicode_literals, print_function

import re
from HTMLParser import HTMLParser

import MySQLdb
import requests

import config

html = HTMLParser()

slack_nicks = {
    2: "asmundboe",
    3: "gromsten",
    5: "eirki",
    6: "nils",
    7: "lbs",
    9: "kenlee",
    10: "cmr",
    11: "smorten",
}

slack_ids = {
    "asmundboe": 2,
    "gromsten": 3,
    "eirki": 5,
    "nils": 6,
    "lbs": 7,
    "kenlee": 9,
    "cmr": 10,
    "smorten": 11,
}


def sanitize(inp, bbcode_uid):
    smilies = re.compile(r'<!-- s.*? --><img src=\\?"\{SMILIES_PATH\}/.*?\\?" alt=\\?"(.*?)\\?" title=\\?".*?" /><!-- s.*? -->')
    inp = re.sub(smilies, r"\1", inp)
    inp = html.unescape(inp)

    inp = inp.replace(":" + bbcode_uid, "")

    img_tags = re.compile(r"\[/?img\]")
    inp = re.sub(img_tags, "", inp)

    youtube_embeds = re.compile(r'\[html\]<iframe width="\d+" height="\d+" src="//www.youtube.com/embed/([^"]+)" frameborder="0" allowfullscreen></iframe>\[/html\]')
    inp = re.sub(youtube_embeds, r"https://www.youtube.com/watch?v=\1", inp)

    return inp


class GargQuotes(object):
    def connect(self):
        self.db = MySQLdb.connect(host=config.db_host, user=config.db_user, passwd=config.db_passwd, db=config.db_name, charset='utf8')
        self.c = self.db.cursor()
        print("Connected to gargen database")

    def teardown(self):
        self.db.close()

    def quote(self, user=None):
        if user and user not in slack_ids:
            return "Gargling not found: %s. Husk å bruke slack id" % user

        if user:
            user_filter = "= %s" % slack_ids[user]
        else:
            user_filter = "IN (2, 3, 5, 6, 7, 9, 10, 11)"

        sql = ("SELECT poster_id, post_text, post_time, post_id, bbcode_uid "
               "FROM phpbb_posts WHERE poster_id %s ORDER BY RAND() LIMIT 1" % user_filter)

        self.c.execute(sql)
        poster_id, post_text, post_time, post_id, bbcode_uid = self.c.fetchall()[0]
        quote = (
            "%(post)s\n"
            "------\n"
            "- %(user)s\n"
            "http://eirik.stavestrand.no/gargen/viewtopic.php?p=%(post_id)s#p%(post_id)s\n"
            % {"user": user if user is not None else slack_nicks[poster_id],
               "post": sanitize(post_text, bbcode_uid), "post_id": post_id, }
            )
        return quote

    def random(self):
        def extract(text):
            match = re.search("(?P<url>https?://[^\s]+)", text)
            return match.group("url")
        url = self.fetch_url(topic_id=636, extract_func=extract)
        return url

    def vidoi(self):
        def extract(text):
            match = re.search(r"(https://www.youtube.com/watch\?v=.{11})", text)
            return match.group(1)
        url = self.fetch_url(topic_id=563, extract_func=extract)
        return url

    def fetch_url(self, topic_id, extract_func):
        sql = "SELECT post_text, bbcode_uid FROM phpbb_posts WHERE topic_id = %s ORDER BY RAND() LIMIT 1" % topic_id
        for _ in range(20):
            self.c.execute(sql)
            post_text, bbcode_uid = self.c.fetchall()[0]
            sanitized = sanitize(post_text, bbcode_uid)
            try:
                url = extract_func(sanitized)
                if requests.get(url).status_code == 200:
                    return url
            except (AttributeError, requests.exceptions.RequestException):
                continue


if __name__ == "__main__":
    garg_quotes = GargQuotes()
    garg_quotes.connect()
    try:
        print(garg_quotes.vidoi())
        print(garg_quotes.random())
    finally:
        garg_quotes.teardown()
