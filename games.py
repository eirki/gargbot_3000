#! /usr/bin/env python3.6
# coding: utf-8
from logger import log

import random
from operator import attrgetter

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
        color = "%06x" % random.randint(0, 0xFFFFFF)
        data = {"name": name, "color": color}
        sql_cmd1 = "INSERT INTO games (name, color) VALUES (%(name)s, %(color)s)"
        with self.db as cursor:
            cursor.execute(sql_cmd1, data)

        sql_cmd2 = "SELECT game_id from games WHERE (name = %(name)s)"
        with self.db as cursor:
            cursor.execute(sql_cmd2, data)
            result = cursor.fetchone()
        game_id = result[0]
        return f"{name} added with game_number {game_id}"

    def modify(self, game_number, new_name):
        old_name = self._get_name_if_exists(game_number)
        if old_name is None:
            error_msg = f"Game # {game_number} finnes ikke =("
            return error_msg

        data = {
            "game_id": game_number,
            "new_name": new_name,
        }

        sql_cmd = "UPDATE games SET name = %(new_name)s WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)
        return f"{old_name} changed to {new_name}!"

    def remove(self, game_number):
        game_name = self._get_name_if_exists(game_number)
        if game_name is None:
            error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
            return error_msg

        data = {"game_id": game_number}
        sql_cmd = "DELETE FROM games WHERE game_id = %(game_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)
        return f"{game_name} removed!"

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

        self._unstar(gargling)
        data = {"game_id": game_number, "slack_id": gargling}
        sql_cmd = "INSERT INTO games_stars (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
        with self.db as cursor:
            try:
                cursor.execute(sql_cmd, data)
                return f":star2: for {game_name}!"
            except MySQLdb.IntegrityError:
                error_msg = "Du har allerede stemt på den. Einstein."
                return error_msg

    def _unstar(self, gargling):
        data = {"slack_id": gargling}
        sql_cmd = "DELETE FROM games_stars WHERE slack_id = %(slack_id)s"
        with self.db as cursor:
            cursor.execute(sql_cmd, data)

    def list(self):
        with self.db as cursor:
            sql_cmd = (
                "SELECT g.game_id, g.name, g.color, v.votes, s.stars FROM games as g "
                "LEFT JOIN (SELECT COUNT(*) as votes, game_id FROM games_votes GROUP BY game_id) "
                "as v ON g.game_id = v.game_id "
                "LEFT JOIN (SELECT COUNT(*) as stars, game_id FROM games_stars GROUP BY game_id) "
                "as s ON g.game_id = s.game_id;"
            )
            cursor.execute(sql_cmd)
            result = cursor.fetchall()

        class Game:
            def __init__(self, number, name, color, votes, stars):
                self.number = number
                self.name = name
                self.votes = votes if votes is not None else 0
                self.n_stars = stars if stars is not None else 0
                self.stars = " ".join([":star2:"] * stars) if stars is not None else ""
                self.color = f"#{color}"

        games = [Game(*game) for game in result]
        games.sort(key=attrgetter("name"))
        games.sort(key=attrgetter("n_stars", "votes"), reverse=True)
        return games

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
