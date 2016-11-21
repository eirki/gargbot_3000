#! /usr/bin/env python
# coding: utf-8
from __future__ import unicode_literals, print_function

import datetime as dt
import time
import traceback
import sys

import MySQLdb
from slackclient import SlackClient

import config
import droppics
import gargquotes

slack_client = SlackClient(config.token)

users = {
    'U33PQTYBV': 'asmundboe',
    'U34DL838S': 'cmr',
    'U33TL3BQC': 'eirki',
    'U34HTUHN2': 'gargbot_3000',
    'U346NSERJ': 'gromsten',
    'U33SRCHB5': 'kenlee',
    'U336SL64Q': 'lbs',
    'U34FMDVTN': 'nils',
    'U34FXQLUD': 'smorten',
    'USLACKBOT': 'slackbot'
}


def handle_command(command, channel, user):
    print(dt.datetime.now())
    command = command.strip()
    print("command: %s" % command)
    if command.startswith("ping"):
        response = {"text": "GargBot 3000 is active. Beep boop beep"}

    elif command.startswith("quote"):
        try:
            user = command.split()[1]
            response = {"text": garg_quotes.quote(user)}
        except IndexError:
            response = {"text": garg_quotes.quote()}

    elif command.startswith("pic"):
        response = {"attachments": [{"fallback":  drop_pics.get_lark(), "image_url": drop_pics.get_lark()}]}

    elif command.startswith("/random"):
        response = {"attachments": [{"fallback":  garg_quotes.random(), "image_url": garg_quotes.random()}]}

    elif command.startswith("vidoi"):
        response = response = {"text": garg_quotes.vidoi()}

    elif command.startswith(("hei", "hallo", "hello", "morn")):
        response = {"text": "Blëep bloöp, hallo %s!" % users.get(user, "")}

    else:
        response = {"text": ("Beep boop beep! Nôt sure whåt you mean by %s. Dette er kommandoene jeg skjønner:\n"
                             "@gargbot_3000 *pic* - (viser tilfedlig bilde fra Larkollen)\n"
                             "@gargbot_3000 *quote* [garling] (henter tilfedlig sitat fra forumet)\n"
                             "@gargbot_3000 *vidoi* (viser tilfedlig musikkvideo fra muzakvidois tråden på forumet\n"
                             "@gargbot_3000 */random* (viser tilfedlig bilde fra \\random tråden på forumet\n"
                             % command)}

    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)
    print("response: %s" % response)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    AT_BOT = "<@%s>" % config.bot_id
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                return output['text'].replace(AT_BOT, "").strip().lower(), output['channel'], output["user"]
    return None, None, None


def panic():
    text = "Error, error! Noe har gått fryktelig galt! Ææææææ. Ta kontakt med systemadministrator ummidelbart, før det er for sent. HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'"
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, text=text)


if __name__ == "__main__":
    garg_quotes = gargquotes.GargQuotes()
    garg_quotes.connect()

    drop_pics = droppics.DropPics()
    drop_pics.connect()
    drop_pics.load_lark_paths()

    if slack_client.rtm_connect():
        print("GargBot 3000 is operational!")
        try:
            while True:
                command, channel, user = parse_slack_output(slack_client.rtm_read())
                if command and channel:
                    try:
                        handle_command(command, channel, user)
                    except MySQLdb.Error:
                        garg_quotes.connect()
                        handle_command(command, channel, user)
                    except:
                        traceback.print_exc()
                        panic()
                time.sleep(1)
        except KeyboardInterrupt:
            sys.exit()
        finally:
            garg_quotes.teardown()
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
