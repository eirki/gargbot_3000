#! /usr/bin/env python3.6
# coding: utf-8
from gargbot_3000.logger import log

import datetime as dt
import time
import random
import threading
import itertools

from slackclient import SlackClient

from gargbot_3000 import config
from gargbot_3000 import database_manager
from gargbot_3000 import droppics
from gargbot_3000 import quotes
from gargbot_3000 import congrats
from gargbot_3000 import games

from typing import Dict, Tuple, Callable
from MySQLdb.connections import Connection

command_explanation = (
    "`@gargbot_3000 games`: viser liste over spillnight-spill\n"
    "`@gargbot_3000 pic [lark/fe/skating/henging] [gargling] [år]`: viser random bilde\n"
    "`@gargbot_3000 quote [garling]`: henter tilfeldig sitat fra forumet\n"
    "`@gargbot_3000 vidoi`: viser tilfeldig musikkvideo fra muzakvidois tråden på forumet\n"
    "`@gargbot_3000 /random`: viser tilfeldig bilde fra \\random tråden på forumet\n"
    "`@gargbot_3000 Hvem [spørsmål]`: svarer på spørsmål om garglings \n"
    "`@gargbot_3000 msn [garling]`: utfrag fra tilfeldig msn samtale\n"
)


def command_handler_wrapper(
        quotes_db: quotes.Quotes,
        drop_pics: droppics.DropPics,
        games_db: games.Games) -> Dict[str, Callable]:

    def cmd_ping() -> Dict:
        """if command is 'ping' """
        response = {"text": "GargBot 3000 is active. Beep boop beep"}
        return response

    def cmd_welcome() -> Dict:
        """when joining new channel"""
        text = (
            "Hei hei kjære alle sammen!\n"
            "Dette er kommandoene jeg skjønner:\n"
            + command_explanation
        )
        response = {"text": text}
        return response

    def cmd_games(user: str, *args) -> Dict:
        """if command is 'game'"""
        output = games_db.main(user, *args)
        if output is None:
            return
        elif isinstance(output, str):
            response = {"text": output}
        else:
            response = {"text": games.command_explanation,
                        "attachments":
                        [{"title": f"{game['stars_str']} {game['name']}",
                          "text": f"Votes: {game['votes']}. (Game #{game['game_id']})",
                          "color": game['color']}
                         for game in output]
                        }
            return response
        return response

    def cmd_pic(*args) -> Dict:
        """if command is 'pic'"""
        picurl, timestamp, error_text = drop_pics.get_pic(*args)
        response = {"attachments": [{"fallback":  picurl,
                                     "image_url": picurl,
                                     "ts": timestamp}]}
        if error_text:
            response["text"] = error_text

        return response

    def cmd_quote(*user) -> Dict:
        """if command is 'quote'"""
        if user:
            response = {"text": quotes_db.garg("quote", *user)}
        else:
            response = {"text": quotes_db.garg("quote")}
        return response

    def cmd_random() -> Dict:
        """if command is '/random'"""
        response = {"attachments": [{"fallback":  quotes_db.garg("random"),
                                     "image_url": quotes_db.garg("random")}]}
        return response

    def cmd_vidoi() -> Dict:
        """if command is 'vidoi'"""
        response = {"text": quotes_db.garg("vidoi")}
        return response

    def cmd_msn(*user) -> Dict:
        """if command is 'msn'"""
        if user:
            date, text = quotes_db.msn(*user)
        else:
            date, text = quotes_db.msn()

        response = {"attachments":
                    [{"author_name": f"{msg_user}:",
                      "text": msg_text,
                      "color": msg_color}
                     for msg_user, msg_text, msg_color in text]
                    }
        response["attachments"][0]["pretext"] = date
        return response

    def cmd_hvem(*qtn) -> Dict:
        """if command.lower().startswith("hvem")"""
        user = random.choice(config.gargling_names)
        answ = " ".join(qtn).replace("?", "!")
        text = f"{user} {answ}"
        response = {"text": text}
        return response

    switch = {
        "ping": cmd_ping,
        "new_channel": cmd_welcome,
        "games": cmd_games,
        "pic": cmd_pic,
        "quote": cmd_quote,
        "/random": cmd_random,
        "vidoi": cmd_vidoi,
        "msn": cmd_msn,
        "hvem": cmd_hvem,
        }
    return switch


def cmd_not_found(command: str) -> Dict:
    text = (
        f"Beep boop beep! Nôt sure whåt you mean by `{command}`. "
        "Dette er kommandoene jeg skjønner:\n"
        + command_explanation
    )
    response = {"text": text}
    return response


def cmd_panic(exc) -> Dict:
    text = (
        f"Error, error! Noe har gått fryktelig galt: {str(exc)}! Ææææææ. Ta kontakt"
        " med systemadministrator umiddelbart, før det er for sent. "
        "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    )
    response = {"text": text}
    return response


def send_response(slack_client: SlackClient, response: Dict, channel: str):
    log.info(dt.datetime.now())
    log.info(f"response: {response}")
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def handle_congrats(slack_client: SlackClient, drop_pics):
    birthdays = congrats.get_birthdays()
    for birthday in itertools.cycle(birthdays):
        log.info(f"Next birthday: {birthday.nick}, at {birthday.next_bday}")
        time.sleep(birthday.seconds_to_bday())
        response = congrats.get_greeting(birthday, drop_pics)

        send_response(slack_client, response=response, channel=config.main_channel)


def setup() -> Tuple[SlackClient, Dict, Connection]:
    db_connection = database_manager.connect_to_database()

    quotes_db = quotes.Quotes(db=db_connection)

    drop_pics = droppics.DropPics(db=db_connection)
    drop_pics.connect_dbx()

    games_db = games.Games(db=db_connection)

    slack_client = SlackClient(config.slack_token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    command_switch = command_handler_wrapper(quotes_db, drop_pics, games_db)

    congrats_thread = threading.Thread(
        target=handle_congrats,
        args=(slack_client, drop_pics)
    )
    congrats_thread.daemon = True
    congrats_thread.start()

    return slack_client, command_switch, db_connection
