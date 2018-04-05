#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

import random
from operator import itemgetter

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


def _get_name_if_exists(db, game_number):
    data = {"game_id": game_number}
    sql_cmd = "SELECT name FROM games WHERE game_id = %(game_id)s"
    with db as cursor:
        cursor.execute(sql_cmd, data)
        result = cursor.fetchone()
    return result['name'] if result is not None else None


def add(db, *args):
    name = " ".join(args)
    color = "%06x" % random.randint(0, 0xFFFFFF)
    data = {"name": name, "color": color}
    sql_cmd1 = "INSERT INTO games (name, color) VALUES (%(name)s, %(color)s)"
    with db as cursor:
        cursor.execute(sql_cmd1, data)

    sql_cmd2 = "SELECT game_id from games WHERE (name = %(name)s)"
    with db as cursor:
        cursor.execute(sql_cmd2, data)
        result = cursor.fetchone()
    game_id = result['game_id']
    return f"{name} added with game_number {game_id}"


def modify(db, game_number, new_name):
    old_name = _get_name_if_exists(db, game_number)
    if old_name is None:
        error_msg = f"Game # {game_number} finnes ikke =("
        return error_msg

    data = {
        "game_id": game_number,
        "new_name": new_name,
    }

    sql_cmd = "UPDATE games SET name = %(new_name)s WHERE game_id = %(game_id)s"
    with db as cursor:
        cursor.execute(sql_cmd, data)
    return f"{old_name} changed to {new_name}!"


def remove(db, game_number):
    game_name = _get_name_if_exists(db, game_number)
    if game_name is None:
        error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
        return error_msg

    data = {"game_id": game_number}
    sql_cmd = "DELETE FROM games WHERE game_id = %(game_id)s"
    with db as cursor:
        cursor.execute(sql_cmd, data)
    return f"{game_name} removed!"


def vote(db, gargling, game_number):
    game_name = _get_name_if_exists(db, game_number)
    if game_name is None:
        error_msg = f"{game_number} er ikke i listen =("
        return error_msg

    data = {"game_id": game_number, "slack_id": gargling}
    sql_cmd = "INSERT INTO games_votes (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
    with db as cursor:
        try:
            cursor.execute(sql_cmd, data)
            return f"{game_name} +1!"
        except MySQLdb.IntegrityError:
            error_msg = "Du har allerede stemt på den. Einstein."
            return error_msg


def unvote(db, gargling, game_number):
    game_name = _get_name_if_exists(db, game_number)
    if game_name is None:
        error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
        return error_msg

    data = {"game_id": game_number, "slack_id": gargling}
    sql_cmd = "DELETE FROM games_votes WHERE game_id = %(game_id)s AND slack_id = %(slack_id)s"
    with db as cursor:
        cursor.execute(sql_cmd, data)
    return f"{game_name} -1"


def star(db, gargling, game_number):
    game_name = _get_name_if_exists(db, game_number)
    if game_name is None:
        error_msg = f"Game # {game_number} finnes ikke =( Husk å bruke spill nummer"
        return error_msg

    _unstar(db, gargling)
    data = {"game_id": game_number, "slack_id": gargling}
    sql_cmd = "INSERT INTO games_stars (game_id,  slack_id) VALUES (%(game_id)s,  %(slack_id)s)"
    with db as cursor:
        try:
            cursor.execute(sql_cmd, data)
            return f":star2: for {game_name}!"
        except MySQLdb.IntegrityError:
            error_msg = "Du har allerede stemt på den. Einstein."
            return error_msg


def _unstar(db, gargling):
    data = {"slack_id": gargling}
    sql_cmd = "DELETE FROM games_stars WHERE slack_id = %(slack_id)s"
    with db as cursor:
        cursor.execute(sql_cmd, data)


def list(db):
    print(db)
    with db as cursor:
        sql_cmd = (
            "SELECT g.game_id, g.name, g.color, v.votes, s.stars FROM games as g "
            "LEFT JOIN (SELECT COUNT(*) as votes, game_id FROM games_votes GROUP BY game_id) "
            "as v ON g.game_id = v.game_id "
            "LEFT JOIN (SELECT COUNT(*) as stars, game_id FROM games_stars GROUP BY game_id) "
            "as s ON g.game_id = s.game_id;"
        )
        cursor.execute(sql_cmd)
        games = list(cursor.fetchall())

    for game in games:
        game["color"] = f"#{game['color']}"
        if game["votes"] is None:
            game["votes"] = 0
        if game["stars"] is None:
            game["stars"] = 0
        game["stars_str"] = " ".join([":star2:"] * game["stars"])

    games.sort(key=itemgetter("name"))
    games.sort(key=itemgetter("stars", "votes"), reverse=True)
    log.info(games)
    return games


def main(db, user, args=None):
    log.info(user)
    log.info(args)
    switch = {
        "add": add,
        "modify": modify,
        "remove": remove,
        "vote": vote,
        "unvote": unvote,
        "star": star,
        "list": list
    }
    if args is None:
        mode = "list"
        args = []
    else:
        mode, *args = args

    try:
        func = switch[mode]
    except KeyError:
        error_msg = f"Incorrect arg specified: `{mode}`. Choose between:\n{command_explanation}"
        return error_msg

    if mode in {"vote", "unvote", "star", "unstar"}:
        args.insert(0, user)

    result = func(db=db, *args)
    return result
