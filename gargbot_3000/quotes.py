#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import datetime as dt
import html
import random
import re
import typing as t

import aiosql
import bbcode
from htmlslacker import HTMLSlacker
from psycopg2.extensions import connection

from gargbot_3000 import config

forum_queries = aiosql.from_path("sql/post.sql", "psycopg2")
msn_queries = aiosql.from_path("sql/message.sql", "psycopg2")


def _sanitize_post(inp, bbcode_uid: str):
    smls = re.compile(
        r'<!-- s.*? --><img src=\\?"\{SMILIES_PATH\}/.*?\\?" '
        'alt=\\?"(.*?)\\?" title=\\?".*?" /><!-- s.*? -->'
    )
    inp = re.sub(smls, r"\1", inp)
    inp = html.unescape(inp)

    inp = inp.replace(":" + bbcode_uid, "")

    img_tags = re.compile(r"\[/?img\]")
    inp = re.sub(img_tags, "", inp)

    youtube_embeds = re.compile(
        r'\[html\]<iframe width="\d+" height="\d+" '
        'src="//www.youtube.com/embed/([^"]+)" frameborder='
        r'"0" allowfullscreen></iframe>\[/html\]'
    )
    inp = re.sub(youtube_embeds, r"https://www.youtube.com/watch?v=\1", inp)

    inp = bbcode.render_html(
        inp, drop_unrecognized=True, escape_html=False, replace_links=False
    )
    inp = inp.replace('rel="nofollow"', "")
    inp = HTMLSlacker(inp).get_output()

    return inp


def forum(
    conn: connection, args: t.Optional[list[str]]
) -> t.Tuple[str, str, str, dt.datetime, str, str]:
    user = args[0] if args else None
    desc = " "
    post = None
    if user:
        post = forum_queries.post_for_user(conn, slack_nick=user)
        if not post:
            desc = (
                f"Gargling not found: {user}. Husk å bruke slack nick. "
                "Her er et tilfeldig quote i stedet."
            )
    if not post:
        post = forum_queries.random_post(conn)
    text = _sanitize_post(post["content"], post["bbcode_uid"])
    avatarurl = f"{config.forum_url}/download/file.php?avatar={post['avatar']}".strip()
    url = f"{config.forum_url}/viewtopic.php?p={post['id']}#p{post['id']}"
    return (text, post["slack_nick"], avatarurl, post["posted_at"], url, desc)


def msn(
    conn: connection, args: t.Optional[list[str]]
) -> t.Tuple[dt.datetime, list, t.Optional[str]]:
    user = args[0] if args else None
    desc = None
    messages = None
    if user:
        messages = msn_queries.message_session_for_user_id(conn, slack_nick=user)
        if messages:
            first = next(i for i, message in enumerate(messages) if message["is_user"])
        else:
            desc = (
                f"Gargling not found: {user}. Husk å bruke slack nick. "
                "Her er en tilfeldig samtale i stedet."
            )
    if not messages:
        messages = msn_queries.random_message_session(conn)
        if len(messages) <= 10:
            first = 0
        else:  # no test coverage
            first = random.randint(0, len(messages) - 10)
    conversation = messages[first : first + 10]

    date = conversation[0]["sent_at"].strftime("%d.%m.%y %H:%M")

    squashed: list[list[str]] = []
    for message in conversation:
        if squashed:
            prev_from_user, prev_content, prev_color = squashed[-1]
            if message["from_user"] == prev_from_user:  # no test coverage
                squashed[-1][1] = "\n".join([prev_content, message["content"]])
                continue
        squashed.append([message["from_user"], message["content"], message["color"]])
    return date, squashed, desc
