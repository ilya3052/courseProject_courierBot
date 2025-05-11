import logging
import os
import sys

import asyncpg
import psycopg as ps
from dotenv import load_dotenv
from psycopg import AsyncConnection

load_dotenv()


class Database:
    _connect: ps.connect = None
    _async_connect: AsyncConnection.connect = None

    @staticmethod
    def get_connection():
        if Database._connect is None:
            try:
                Database._connect = ps.connect(
                    dbname=os.getenv("DB_NAME"),
                    user=os.getenv("USER"),
                    password=os.getenv("PASSWORD"),
                    host=os.getenv("HOST"),
                    port=os.getenv("PORT")
                )
            except ps.Error:
                logging.critical("Соединение не установлено!")
                sys.exit(1)
        return Database._connect

    @staticmethod
    async def get_async_connection():
        if Database._async_connect is None:
            try:
                Database._async_connect = await asyncpg.connect(
                    user=os.getenv("USER"),
                    password=os.getenv("PASSWORD"),
                    database=os.getenv("DB_NAME"),
                    host=os.getenv("HOST"),
                    port=os.getenv("PORT")
                )
                logging.info("Асинхронное соединение через asyncpg установлено")
            except Exception as e:
                logging.critical(f"Асинхронное соединение не установлено: {e}")
                sys.exit(1)
        return Database._async_connect

    @staticmethod
    async def listen_channel(channel_name: str, callback):
        conn = await Database.get_async_connection()
        await conn.add_listener(channel_name, callback)
        logging.info(f"🔔 Подписка на канал '{channel_name}' установлена")

    @staticmethod
    async def close_connection():
        if Database._connect is not None:
            Database._connect.close()
        if Database._async_connect is not None:
            await Database._async_connect.close()
