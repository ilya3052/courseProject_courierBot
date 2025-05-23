import logging

import psycopg as ps
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from icecream import ic
from psycopg import sql
from psycopg.errors import LockNotAvailable

from Filters.IsRegistered import IsRegistered
from core.bot_instance import bot
from core.database import Database
from keyboards import get_order_notify_kb
from .register import cmd_start

router = Router()


class Deliveries(StatesGroup):
    confirm = State()


async def get_notify(conn, pid, channel, payload):
    order_id = int(str(payload).split(":")[1].strip())
    print(f"[{channel}] => {payload} => {order_id}")
    await send_notify(order_id)


async def low_rating(conn, pid, channel, payload):
    print(f"[{channel}] => {payload}")
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


async def send_notify(order_id: int):
    connect: ps.connect = Database.get_connection()

    free_couriers = await get_free_couriers()

    if not free_couriers:
        await Database.notify_channel("order_status", f"action: order_not_accept; order_id: {order_id}")
        return

    get_product_info = (sql.SQL(
        """SELECT COUNT(*), o.order_address 
FROM \"order\" o 
    JOIN added a on o.order_id = a.order_id 
    WHERE o.order_id = %s
GROUP BY o.order_address;"""
    ))

    get_product_list = (sql.SQL("""SELECT DISTINCT p.product_name, COUNT(p.product_name), p.product_price 
FROM product p 
	JOIN added a on a.product_article = p.product_article 
	JOIN "order" o ON o.order_id = a.order_id 
WHERE o.order_id = %s
GROUP BY p.product_name, p.product_price;
        """))

    get_product_total_price = (sql.SQL("""SELECT SUM(p.product_price) 
FROM product p 
    JOIN added a ON a.product_article = p.product_article 
    JOIN \"order\" o ON o.order_id = a.order_id 
WHERE o.order_id = %s;"""))

    try:
        with connect.cursor() as cur:
            product_info = cur.execute(get_product_info, (order_id,)).fetchone()
            product_total_price = cur.execute(get_product_total_price, (order_id,)).fetchone()[0]
            products_list = cur.execute(get_product_list, (order_id,)).fetchall()
    except ps.Error as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")

    order_desc = "Список товаров:\n"

    for item in products_list:
        order_desc += f"{item[0]} - {item[1]} шт., {item[2]} за шт.\n"

    for courier in free_couriers:
        await bot.send_message(chat_id=courier,
                               text=f'Получен новый заказ!\n'
                                    f'Количество товаров - {product_info[0]}\n'
                                    f'Адрес доставки - {product_info[1]}\n'
                                    f'Сумма заказа - {product_total_price}\n{order_desc}',
                               reply_markup=get_order_notify_kb(order_id))


@router.callback_query(F.data.startswith("action_accept"), IsRegistered())
async def order_accept_handler(callback: CallbackQuery):
    connect: ps.connect = Database.get_connection()

    order_id = callback.data.split(":")[1]

    try:
        with connect.cursor() as cur:
            status = cur.execute("SELECT accept_order(%s, %s)", (callback.message.chat.id, order_id,)).fetchone()[0]
            ic(status)
            if status == 1:
                raise LockNotAvailable()
            await callback.answer()
            await Database.notify_channel("order_status", f'action: order_accept; order_id: {order_id}')
            connect.commit()
    except LockNotAvailable:
        connect.rollback()
        await callback.answer("Заказ уже принят другим курьером!")

    await callback.answer()


@router.callback_query(F.data.startswith("action_cancel"), IsRegistered())
async def order_cancel_handler(callback: CallbackQuery):
    print("Отказ от заказа")
    await callback.message.delete()


async def get_free_couriers():
    connect: ps.connect = Database.get_connection()
    with connect.cursor() as cur:
        free_couriers = cur.execute(
            """SELECT u.user_tgchat_id 
                    FROM courier c 
	                JOIN users u ON c.user_id = u.user_id 
                WHERE c.courier_is_busy_with_order = false AND u.user_role = 'courier';"""
        ).fetchall()
    free_couriers = [courier[0] for courier in free_couriers]
    return free_couriers


@router.message(~IsRegistered())
@router.callback_query(~IsRegistered())
async def reg_handler(update: Message | CallbackQuery, state: FSMContext):
    message = update.message if isinstance(update, CallbackQuery) else update
    await cmd_start(message, state)
