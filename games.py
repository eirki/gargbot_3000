#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

from operator import itemgetter
from collections import Counter

import MySQLdb

commands = (
    "`@gargbot_3000 games add [game_name]`\n"
    "`@gargbot_3000 games modify [game_number] (game_name=[game_name] | url=[url] | pic_url=[pic_url])`\n"
    "`@gargbot_3000 games remove [game_number]`\n"
    "`@gargbot_3000 games vote [game_number]`\n"
    "`@gargbot_3000 games star [game_number]`\n"
    "`@gargbot_3000 games list`\n"
)


class Games:

    def __init__(self, db):
        self.db = db

    def add(self, *args):
        name = " ".join(args)
        data = {"name": name}
        sql_cmd = "INSERT INTO games (name) VALUES (%(name)s)"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)

    def modify(self, game_number, *args):
        if not args:
            error_msg = "No args specified, use `name=[game_name]` or `url=[url]` or `pic_url=[pic_url]`"
            return error_msg
        args_str = " ".join(args)
        args_lst = args_str.split("=")
        if len(args_lst) != 2 or args_lst[0] not in {"name", "url", "pic_url"}:
            error_msg = "Args incorrectly specified, use `name=[game_name]` or `url=[url]` or `pic_url=[pic_url]`"
            return error_msg
        column, value = args_lst
        value = value.replace("<", "").replace(">", "")

        data = {
            "game_id": game_number,
            "value": value,
        }

        sql_cmd = f"UPDATE games SET {column} = %(value)s WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)

    def remove(self, game_number):
        data = {"game_id": game_number}
        sql_cmd1 = "DELETE FROM games WHERE game_id = %(game_id)s"
        sql_cmd2 = "DELETE FROM games_votes WHERE game_id = %(game_id)s"
        sql_cmd3 = "DELETE FROM games_stars WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd1, data)
            cursor.execute(sql_cmd2, data)
            cursor.execute(sql_cmd3, data)

    def vote(self, gargling, game_number):
        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "INSERT INTO games_votes (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
        with self.db as cursor:
            try:
                cursor.execute(sql_cmd, data)
            except MySQLdb.IntegrityError:
                error_msg = "Du har allerede stemt på den. Einstein."
                return error_msg

    def unvote(self, gargling, game_number):
        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "DELETE FROM games_votes WHERE game_id = %(game_id)s AND slack_id = %(slack_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)

    def star(self, gargling, game_number):
        self.unstar(gargling)
        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "INSERT INTO games_stars (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
        with self.db as cursor:
            try:
                cursor.execute(sql_cmd, data)
            except MySQLdb.IntegrityError:
                error_msg = "Du har allerede stemt på den. Einstein."
                return error_msg

    def unstar(self, gargling):
        data = {"slack_id": gargling}
        sql_cmd = "DELETE FROM games_stars WHERE slack_id = %(slack_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)

    def list(self):
        with self.db as cursor:
            sql_cmd = "SELECT game_id, name, url, pic_url FROM games"
            cursor.execute(sql_cmd)
            games = cursor.fetchall()

            sql_cmd = "SELECT game_id FROM games_votes"
            cursor.execute(sql_cmd)
            votes = Counter([vote[0] for vote in cursor.fetchall()])

            sql_cmd = "SELECT game_id FROM games_stars"
            cursor.execute(sql_cmd)
            stars = Counter([star[0] for star in cursor.fetchall()])
        entries = [
            (game_number, name, url, pic_url, votes.get(game_number, 0), stars.get(game_number, 0))
            for game_number, name, url, pic_url in games
        ]
        entries.sort(key=itemgetter(5), reverse=True)
        return entries

    def main(self, user, *args):
        print(user, args)
        switch = {
            "add": self.add,
            "modify": self.modify,
            "remove": self.remove,
            "vote": self.vote,
            "unvote": self.unvote,
            "star": self.star,
            "unstar": self.unstar,
            "list": self.list
        }
        if len(args) == 0:
            error_msg = f"No args specified. Choose between:\n{commands}"
            return error_msg
        else:
            mode, *args = args

        try:
            func = switch[mode]
        except KeyError:
            error_msg = f"Incorrect arg specified: `{mode}`. Choose between:\n{commands}"
            return error_msg

        if mode in {"vote", "unvote", "star", "unstar"}:
            args.insert(0, user)

        result = func(*args)
        return result
