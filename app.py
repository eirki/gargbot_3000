#! /usr/bin/env python3.5
# coding: utf-8
import datetime as dt
import time
import traceback
import sys

import MySQLdb
from slackclient import SlackClient

import config
import droppics
import gargquotes

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


def filter_slack_output(slack_rtm_output):
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


def command_handler_wrapper(garg_quotes, drop_pics):
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
            try:
                topic = command.split()[1]
                pic = drop_pics.get_pic(topic)
            except IndexError:
                pic = drop_pics.get_pic()
            response = {"attachments": [{"fallback":  pic, "image_url": pic}]}

        elif command.startswith("/random"):
            response = {"attachments": [{"fallback":  garg_quotes.random(), "image_url": garg_quotes.random()}]}

        elif command.startswith("vidoi"):
            response = {"text": garg_quotes.vidoi()}

        elif command.startswith(("hei", "hallo", "hello", "morn")):
            response = {"text": "Blëep bloöp, hallo %s!" % users.get(user, "")}

        else:
            response = {"text": ("Beep boop beep! Nôt sure whåt you mean by %s. Dette er kommandoene jeg skjønner:\n"
                                 "@gargbot_3000 *pic* [lark/fe/skating] - (viser tilfedlig Larkollen/Forsterka Enhet/skate bilde)\n"
                                 "@gargbot_3000 *quote* [garling] (henter tilfedlig sitat fra forumet)\n"
                                 "@gargbot_3000 *vidoi* (viser tilfedlig musikkvideo fra muzakvidois tråden på forumet\n"
                                 "@gargbot_3000 */random* (viser tilfedlig bilde fra \\random tråden på forumet\n"
                                 % command)}

        return response
    return handle_command


def panic():
    text = ("Error, error! Noe har gått fryktelig galt! Ææææææ. Ta kontakt"
            " med systemadministrator ummidelbart, før det er for sent. "
            "HJELP MEG. If I don't survive, tell mrs. gargbot... 'Hello'")
    response = {"text": text}
    return response


def send_response(slack_client, response, channel):
    print("response: %s" % response)
    slack_client.api_call("chat.postMessage", channel=channel, as_user=True, **response)


def main():
    garg_quotes = gargquotes.GargQuotes()
    garg_quotes.connect()

    drop_pics = droppics.DropPics()
    drop_pics.connect()
    drop_pics.load_img_paths()

    slack_client = SlackClient(config.token)
    connected = slack_client.rtm_connect()
    if not connected:
        raise Exception("Connection failed. Invalid Slack token or bot ID?")

    handle_command = command_handler_wrapper(garg_quotes, drop_pics)

    print("GargBot 3000 is operational!")
    try:
        while True:
            time.sleep(1)
            command, channel, user = filter_slack_output(slack_client.rtm_read())
            if not (command and channel):
                continue
            try:
                response = handle_command(command, channel, user)
            except MySQLdb.Error:
                garg_quotes.connect()
                response = handle_command(command, channel, user)
            except:
                traceback.print_exc()
                response = panic()
            send_response(slack_client, response, channel)
    except KeyboardInterrupt:
        sys.exit()
    finally:
        garg_quotes.teardown()


if __name__ == "__main__":
    main()
