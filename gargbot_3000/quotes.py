#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

import re
import html
import random
from operator import itemgetter

from gargbot_3000 import config

from typing import Optional, List


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
    def quote(cursor, user=None):
        if user and user not in Garg.slack_nicks_to_db_ids:
            return f"Gargling not found: {user}. Husk å bruke slack nick"

        if user:
            user_filter = f"= {Garg.slack_nicks_to_db_ids[user]}"
        else:
            user_filter = "IN (2, 3, 5, 6, 7, 9, 10, 11)"

        sql = ("SELECT db_id, post_text, post_time, post_id, bbcode_uid "
               f"FROM phpbb_posts WHERE db_id {user_filter} ORDER BY RAND() LIMIT 1")

        cursor.execute(sql)
        result = cursor.fetchone()
        db_id = result["db_id"]
        post_id = result["post_id"]
        user = user if user is not None else config.db_ids_to_slack_nicks[db_id]
        post = Garg._sanitize(result["post_text"], result["bbcode_uid"])
        quote = (
            f"{post}\n"
            "------\n"
            f"- {user}\n"
            f"http://eirik.stavestrand.no/gargen/viewtopic.php?p={post_id}#p{post_id}\n")
        return quote


class MSN:
    @staticmethod
    def quote(cursor, user=None):
        if user is not None:
            db_id = Garg.slack_nicks_to_db_ids[user]
            user_filter = f"WHERE db_id = {db_id}"
        else:
            user_filter = ""
        sql = f"SELECT session_ID FROM msn_messages {user_filter} ORDER BY RAND() LIMIT 1"
        cursor.execute(sql)
        session_ID = cursor.fetchone()["session_ID"]
        log.info(session_ID)
        sql = ("SELECT msg_time, from_user, to_users, msg_text, msg_color, db_id "
               f'FROM msn_messages WHERE session_ID = "{session_ID}"')
        cursor.execute(sql)
        messages = list(cursor.fetchall())
        messages.sort(key=itemgetter("msg_time"))
        if user is not None:
            first = next(i for i, message in enumerate(messages) if message["db_id"] == db_id)
        elif len(messages) <= 10:
            first = 0
        else:
            first = random.randint(0, len(messages)-10)
        chosen_messages = messages[first:first+10]

        date = chosen_messages[0]["msg_time"].strftime("%d.%m.%y %H:%M")

        convo = []
        for message in chosen_messages:
            if convo:
                prev_from_user, prev_msg_text, prev_msg_color = convo[-1]
                if message["from_user"] == prev_from_user:
                    convo[-1][1] = "\n".join([prev_msg_text, message["msg_text"]])
                    continue
            convo.append([message["from_user"], message["msg_text"], message["msg_color"]])

        return date, convo


class Quotes:
    def __init__(self, db):
        with db as cursor:
            self.slack_nicks_to_db_ids = self._get_users(cursor)
        self.db_ids_to_slack_nicks = {
            nick: db_id for db_id, nick in
            self.slack_nicks_to_db_ids.items()
        }

        MSN.slack_nicks_to_db_ids = self.slack_nicks_to_db_ids
        Garg.slack_nicks_to_db_ids = self.slack_nicks_to_db_ids
        Garg.db_ids_to_slack_nicks = self.db_ids_to_slack_nicks

    def _get_users(self, cursor):
        sql_command = "SELECT slack_nick, db_id FROM user_ids"
        cursor.execute(sql_command)
        return {row['slack_nick']: row['db_id'] for row in cursor.fetchall()}

    def garg(self, db, func, args: Optional[List[str]]):
        user = args[0] if args else None
        with db as cursor:
            result = Garg.quote(cursor, user)
        return result

    def msn(self, db, args: Optional[List[str]]):
        user = args[0] if args else None
        with db as cursor:
            result = MSN.quote(cursor, user)
        return result
