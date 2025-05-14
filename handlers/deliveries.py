import logging

import psycopg as ps
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery
from icecream import ic
from psycopg import sql, IsolationLevel
from psycopg.errors import LockNotAvailable

from bot_instance import bot
from database import Database
from keyboards import get_order_notify_kb

router = Router()


class Deliveries(StatesGroup):
    confirm = State()

async def get_notify(conn, pid, channel, payload):
    order_id = int(str(payload).split(":")[1].strip())
    print(f"[{channel}] => {payload} => {order_id}")
    await send_notify(order_id)


async def send_notify(order_id: int):
    connect: ps.connect = Database.get_connection()

    free_couriers = await get_free_couriers()

    get_product_count = (sql.SQL(
        "SELECT COUNT(*) FROM \"order\" o JOIN added a on o.order_id = a.order_id WHERE o.order_id = {};"
    ))

    get_product_list = (sql.SQL("""SELECT DISTINCT p.product_name, COUNT(p.product_name), p.product_price 
FROM product p 
	JOIN added a on a.product_article = p.product_article 
	JOIN "order" o ON o.order_id = a.order_id 
WHERE o.order_id = {}
GROUP BY p.product_name, p.product_price;
        """))

    get_product_total_price = (sql.SQL("""SELECT SUM(p.product_price) 
FROM product p 
    JOIN added a ON a.product_article = p.product_article 
    JOIN \"order\" o ON o.order_id = a.order_id 
WHERE o.order_id = {};"""))

    with connect.cursor() as cur:
        try:
            product_count = cur.execute(get_product_count.format(order_id)).fetchone()[0]
            product_total_price = cur.execute(get_product_total_price.format(order_id)).fetchone()[0]
            products_list = cur.execute(get_product_list.format(order_id)).fetchall()
            ic(product_count, product_total_price, products_list)
        except ps.Error as p:
            logging.exception(f"Произошла ошибка при выполнении запроса: {p}")

    order_desc = "Список товаров:\n"

    for item in products_list:
        order_desc += f"{item[0]} - {item[1]} шт., {item[2]} за шт.\n"

    for courier in free_couriers:
        await bot.send_message(chat_id=courier,
                               text=f'Получен новый заказ!\n'
                                    f'Количество товаров - {product_count}, сумма заказа - {product_total_price}\n{order_desc}',
                               reply_markup=get_order_notify_kb(order_id))


@router.callback_query(F.data.startswith("action_accept"))
async def order_accept_handler(callback: CallbackQuery, state: FSMContext):
    connect: ps.connect = Database.get_connection()
    order_id = callback.data.split(":")[1]
    ic(order_id)
    data = await state.get_data()

    try:
        with connect.transaction(isolation_level=IsolationLevel.READ_COMMITTED):
            connect.execute("SELECT 1 FROM \"order\" WHERE order.order_id = {} FOR UPDATE NOWAIT;".format(order_id))
    except LockNotAvailable:
        pass

    ic(callback.data.split("_"))

    await callback.answer()


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
    return free_couriers


def confirm_delivery():
    pass
