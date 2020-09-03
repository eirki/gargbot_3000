#! /usr/bin/env python3
# coding: utf-8
from contextlib import contextmanager
import typing as t

import aiosql
from flask import current_app
from psycopg2.extensions import connection

from gargbot_3000 import database

queries = aiosql.from_path("sql/health.sql", driver_adapter=database.SqlFormatAdapter)


@contextmanager
def connection_context(
    conn=t.Optional[connection],
) -> t.Generator[connection, None, None]:
    if conn is not None:
        yield conn
    elif current_app:
        with current_app.pool.get_connection() as conn:
            yield conn
    else:
        conn = database.connect()
        try:
            yield conn
        finally:
            conn.close()
