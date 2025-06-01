import logging

import psycopg as ps

from core.bot_instance import bot
from core.database import Database
from handlers.deliveries import send_notify


async def get_notify(conn, pid, channel, payload):
    order_id = int(str(payload).split(":")[1].strip())
    await send_notify(order_id)


async def low_rating(conn, pid, channel, payload):
    connect: ps.connect = Database.get_connection()
    try:
        with connect.cursor() as cur:
            user = cur.execute("""SELECT u.user_tgchat_id 
            FROM users u 
            JOIN courier c ON c.user_id = u.user_id 
            WHERE c.courier_id = %s""",
                               (payload,)
                               ).fetchone()[0]
        await bot.send_message(user,
                               "Ваш рейтинг опустился ниже допустимого значения, возможность принимать заказы временно заблокирована. Обратитесь к администратору!")
    except ps.Error as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
