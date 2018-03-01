#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

from operator import itemgetter
from collections import Counter

import MySQLdb

command_explanation = (
    "`@gargbot_3000 games`: viser liste over spillnight-spill\n"
    "`@gargbot_3000 games add [game_name]`: legger til i listen\n"
    "`@gargbot_3000 games modify [game_number] [game_name]`: endrer navn på spill i listen\n"
    "`@gargbot_3000 games remove [game_number]`: fjerner spill spill fra listen\n"
    "`@gargbot_3000 games vote [game_number]`: stemme for å spille et spill (man kan stemme på så mange spill man vil)\n"
    "`@gargbot_3000 games unvote [game_number]`: fjerner stemme fra spill\n"
    "`@gargbot_3000 games star [game_number]` gi stjerne til et spill (man har kun én stjerne)\n"
)


class Games:

    def __init__(self, db):
        self.db = db

    def _get_name_if_exists(self, game_number):
        data = {"game_id": game_number}
        sql_cmd = "SELECT name FROM games WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)
            result = cursor.fetchone()
        return result[0] if result is not None else result

    def add(self, *args):
        name = " ".join(args)
        data = {"name": name}
        sql_cmd = "INSERT INTO games (name) VALUES (%(name)s)"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)

    def modify(self, game_number, game_name):
        exists = self._get_name_if_exists(game_number)
        if exists is None:
            error_msg = f"Game # {game_number} finnes ikke =("
            return error_msg

        data = {
            "game_id": game_number,
            "game_name": game_name,
        }

        sql_cmd = "UPDATE games SET game_name = %(game_name)s WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)
            try:
                cursor.execute(sql_cmd, data)
                return f"{game_name} added!"
            except MySQLdb.IntegrityError:
                return f"{game_name} already added!"

    def remove(self, game_number):
        exists = self._get_name_if_exists(game_number)
        if exists is None:
            error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
            return error_msg

        data = {"game_id": game_number}
        sql_cmd1 = "DELETE FROM games WHERE game_id = %(game_id)s"
        sql_cmd2 = "DELETE FROM games_votes WHERE game_id = %(game_id)s"
        sql_cmd3 = "DELETE FROM games_stars WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd1, data)
            cursor.execute(sql_cmd2, data)
            cursor.execute(sql_cmd3, data)

    def vote(self, gargling, game_number):
        game_name = self._get_name_if_exists(game_number)
        if game_name is None:
            error_msg = f"{game_number} er ikke i listen =("
            return error_msg

        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "INSERT INTO games_votes (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
        with self.db as cursor:
            try:
                cursor.execute(sql_cmd, data)
                return f"{game_name} +1!"
            except MySQLdb.IntegrityError:
                error_msg = "Du har allerede stemt på den. Einstein."
                return error_msg

    def unvote(self, gargling, game_number):
        game_name = self._get_name_if_exists(game_number)
        if game_name is None:
            error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
            return error_msg

        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "DELETE FROM games_votes WHERE game_id = %(game_id)s AND slack_id = %(slack_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)
        return f"{game_name} -1"

    def star(self, gargling, game_number):
        game_name = self._get_name_if_exists(game_number)
        if game_name is None:
            error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
            return error_msg

        self.unstar(gargling)
        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "INSERT INTO games_stars (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
        with self.db as cursor:
            try:
                cursor.execute(sql_cmd, data)
            except MySQLdb.IntegrityError:
                error_msg = "Du har allerede stemt på den. Einstein."
                return error_msg

    def list(self):
        with self.db as cursor:
            sql_cmd = "SELECT game_id, name FROM games"
            cursor.execute(sql_cmd)
            games = cursor.fetchall()

            sql_cmd = "SELECT game_id FROM games_votes"
            cursor.execute(sql_cmd)
            votes = Counter([vote[0] for vote in cursor.fetchall()])

            sql_cmd = "SELECT game_id FROM games_stars"
            cursor.execute(sql_cmd)
            stars = Counter([star[0] for star in cursor.fetchall()])
        entries = [
            (game_number, name,  votes.get(game_number, 0), stars.get(game_number, 0))
            for game_number, name, in games
        ]
        entries.sort(key=itemgetter(3, 2, 0), reverse=True)
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
            "list": self.list
        }
        if len(args) == 0:
            mode = "list"
        else:
            mode, *args = args

        try:
            func = switch[mode]
        except KeyError:
            error_msg = f"Incorrect arg specified: `{mode}`. Choose between:\n{command_explanation}"
            return error_msg

        if mode in {"vote", "unvote", "star", "unstar"}:
            args.insert(0, user)

        result = func(*args)
        return result
