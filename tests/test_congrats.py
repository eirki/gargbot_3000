#! /usr/bin/env python3.6
# coding: utf-8
import pytest

from context import congrats
from test_pics import drop_pics
from test_quotes import quotes_db

def test_congrat(drop_pics):
    birthdays = congrats.get_birthdays()
    response = congrats.get_greeting(birthdays[0], drop_pics)
    print(response)
