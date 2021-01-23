#! /usr/bin/env python3
# coding: utf-8
from __future__ import annotations

import pytest

from gargbot_3000 import __main__


def test_main():
    with pytest.raises(SystemExit):
        __main__.main()
