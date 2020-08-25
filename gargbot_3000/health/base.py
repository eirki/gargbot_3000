#! /usr/bin/env python3
# coding: utf-8
from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
import typing as t

from accesslink import AccessLink as PolarApi
import aiosql
from fitbit.api import FitbitOauth2Client
from flask import current_app
import pendulum
from psycopg2.extensions import connection
from withings_api import WithingsAuth
from withings_api.common import Credentials

from gargbot_3000 import database

token_type = t.Union[Credentials, dict]
service_user_id_type = t.Union[int, str]


queries = aiosql.from_path("sql/health.sql", driver_adapter=database.JinjaSqlAdapter)


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


class HealthService(metaclass=ABCMeta):
    name: str
    client: t.Union[WithingsAuth, FitbitOauth2Client, PolarApi]

    @abstractmethod
    def authorization_url(cls) -> str:
        pass

    @abstractmethod
    def token(cls, code: str) -> t.Tuple[service_user_id_type, token_type]:
        pass

    @staticmethod
    @abstractmethod
    def persist_token(token, conn) -> None:
        pass


class HealthUser(metaclass=ABCMeta):
    service: t.ClassVar[t.Type[HealthService]]

    def __init__(self, gargling_id: int, first_name: str):
        self.gargling_id = gargling_id
        self.first_name = first_name

    @abstractmethod
    def steps(
        self, date: pendulum.Date, conn: t.Optional[connection] = None
    ) -> t.Optional[int]:
        pass

    @abstractmethod
    def body(self, date: pendulum.Date) -> t.Optional[dict]:
        pass
