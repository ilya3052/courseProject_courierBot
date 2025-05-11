from bot import bot
import psycopg as ps
from psycopg import sql
from icecream import ic

from database import Database


async def send_notify(free_couriers: list[int]):
    for courier in free_couriers:
        print(courier)
        await bot.send_message(chat_id=courier, text='Тестовый текст')


async def get_free_couriers():
    connect: ps.connect = Database.get_connection()
    with connect.cursor() as cur:
        free_couriers = cur.execute(
            """SELECT u.user_tgchat_id 
                    FROM courier c 
	                JOIN users u ON c.user_id = c.user_id 
                WHERE c.courier_is_busy_with_order = false AND u.user_role = 'courier';"""
        ).fetchall()
    free_couriers = [courier[0] for courier in free_couriers]
    ic(free_couriers)
    await send_notify(free_couriers)

def confirm_delivery():
    pass
