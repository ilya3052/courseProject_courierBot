import logging

from asyncpg import PostgresError

from core.bot_instance import bot
from core.database import db
from handlers.deliveries import send_notify


async def get_notify(conn, pid, channel, payload):
    order_id = int(str(payload).split(":")[1].strip())
    await send_notify(order_id)


async def low_rating(conn, pid, channel, payload):
    try:
        user = await db.execute("""SELECT u.user_tgchat_id 
        FROM users u 
        JOIN courier c ON c.user_id = u.user_id 
        WHERE c.courier_id = $1""", payload, fetchval=True)
        await bot.send_message(user,
                               "Ваш рейтинг опустился ниже допустимого значения, возможность принимать заказы временно заблокирована. Обратитесь к администратору!")
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
