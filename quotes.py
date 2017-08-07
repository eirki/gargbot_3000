#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import re
import html
import random
from operator import itemgetter

import requests

import config


class Garg:
    @staticmethod
    def _sanitize(inp, bbcode_uid):
        smls = re.compile(r'<!-- s.*? --><img src=\\?"\{SMILIES_PATH\}/.*?\\?" alt=\\?"(.*?)\\?" title=\\?".*?" /><!-- s.*? -->')
        inp = re.sub(smls, r"\1", inp)
        inp = html.unescape(inp)

        inp = inp.replace(":" + bbcode_uid, "")

        img_tags = re.compile(r"\[/?img\]")
        inp = re.sub(img_tags, "", inp)

        youtube_embeds = re.compile(r'\[html\]<iframe width="\d+" height="\d+" src="//www.youtube.com/embed/([^"]+)" frameborder='
                                    r'0" allowfullscreen></iframe>\[/html\]')
        inp = re.sub(youtube_embeds, r"https://www.youtube.com/watch?v=\1", inp)

        return inp

    @staticmethod
    def _fetch_url(cursor, topic_id, extract_func):
        sql = f"SELECT post_text, bbcode_uid FROM phpbb_posts WHERE topic_id = {topic_id} ORDER BY RAND() LIMIT 1"
        for _ in range(20):
            cursor.execute(sql)
            post_text, bbcode_uid = cursor.fetchall()[0]
            sanitized = Garg._sanitize(post_text, bbcode_uid)
            try:
                url = extract_func(sanitized)
                if requests.get(url).status_code == 200:
                    return url
            except (AttributeError, requests.exceptions.RequestException):
                continue

    @staticmethod
    def quote(cursor, user=None):
        if user and user not in config.slack_nicks_to_garg_ids:
            return f"Gargling not found: {user}. Husk å bruke slack id"

        if user:
            garg_id = config.slack_nicks_to_garg_ids[user]
            user_filter = f"= {garg_id}"
        else:
            user_filter = "IN (2, 3, 5, 6, 7, 9, 10, 11)"

        sql = ("SELECT poster_id, post_text, post_time, post_id, bbcode_uid "
               f"FROM phpbb_posts WHERE poster_id {user_filter} ORDER BY RAND() LIMIT 1")

        cursor.execute(sql)
        poster_id, post_text, post_time, post_id, bbcode_uid = cursor.fetchall()[0]
        user = user if user is not None else config.garg_ids_to_slack_nicks[poster_id]
        post = Garg._sanitize(post_text, bbcode_uid)
        quote = (
            f"{post}\n"
            "------\n"
            f"- {user}\n"
            f"http://eirik.stavestrand.no/gargen/viewtopic.php?p={post_id}#p{post_id}\n")
        return quote

    @staticmethod
    def random(cursor):
        def extract(text):
            match = re.search("(?P<url>https?://[^\s]+)", text)
            return match.group("url")
        url = Garg._fetch_url(cursor, topic_id=636, extract_func=extract)
        return url

    @staticmethod
    def vidoi(cursor):
        def extract(text):
            match = re.search(r"//www.youtube.com/embed/(.{11})", text)
            ytb_id = match.group(1)
            ytb_url = f"https://www.youtube.com/watch?v={ytb_id}"
            return ytb_url
        url = Garg._fetch_url(cursor, topic_id=563, extract_func=extract)
        return url


class MSN:
    @staticmethod
    def quote(cursor, user=None):
        if user is not None:
            user_nicks = config.slack_to_msn_nicks[user]
            filter = " WHERE " + " OR ".join([f'from_user LIKE "%{name}%"'
                                              for name in user_nicks])
        else:
            filter = ""
        sql = f"SELECT session_ID FROM msn_messages {filter} ORDER BY RAND() LIMIT 1"
        log.info(sql)
        cursor.execute(sql)
        session_ID = cursor.fetchone()[0]
        log.info(session_ID)
        sql = ("SELECT msg_time, from_user, to_users, msg_text, msg_color "
               f'FROM msn_messages WHERE session_ID = "{session_ID}"')
        log.info(sql)
        cursor.execute(sql)
        messages = list(cursor.fetchall())
        messages.sort(key=itemgetter(0))
        if user is not None:
            first = next(i for i, message in enumerate(messages) if any(nick in message[1].lower()
                                                                        for nick in user_nicks))
        elif len(messages) <= 10:
            first = 0
        else:
            first = random.randint(0, len(messages)-10)
        chosen = messages[first:first+10]

        date = chosen[0][0].strftime("%d.%m.%y %H:%M")

        convo = []
        for msg_time, from_user, to_users, msg_text, msg_color in chosen:
            if convo:
                prev_from_user, prev_msg_text, prev_msg_color = convo[-1]
                if from_user == prev_from_user:
                    convo[-1][1] = "\n".join([prev_msg_text, msg_text])
                    continue
            convo.append([from_user, msg_text, msg_color])

        return date, convo


class Quotes:
    def __init__(self, db):
        self.db = db

    def garg(self, func, *args):
        c = self.db.cursor()
        switch = {
            "quote": Garg.quote,
            "random": Garg.random,
            "vidoi": Garg.vidoi,
        }
        selected = switch[func]
        result = selected(c, *args)
        c.close()
        return result

    def msn(self, user=None):
        c = self.db.cursor()
        result = MSN.quote(c, user)
        c.close()
        return result


if __name__ == "__main__":
    db_connection = config.connect_to_database()
    quotes_db = Quotes(db=db_connection)
    try:
        log.info(quotes_db.garg("quote"))
        log.info(quotes_db.garg("vidoi"))
        log.info(quotes_db.garg("random"))
        log.info(quotes_db.msn(user="cmr"))
    finally:
        db_connection.close()
