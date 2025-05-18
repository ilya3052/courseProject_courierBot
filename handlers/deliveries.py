import logging

import psycopg as ps
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from psycopg import sql
from psycopg.errors import LockNotAvailable

from Filters.IsRegistered import IsRegistered
from core.bot_instance import bot
from core.database import Database
from handlers import cmd_start
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

    if not free_couriers:
        await Database.notify_channel("order_not_accept", f"action: order_not_accept; order_id: {order_id}")
        return

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


# ОФОРМИТЬ КАК ТРАНЗАКЦИЮ ВНУТРИ ПОСТГРЕСА
@router.callback_query(F.data.startswith("action_accept"), IsRegistered())
async def order_accept_handler(callback: CallbackQuery, state: FSMContext):
    connect: ps.connect = Database.get_connection()

    order_id = callback.data.split(":")[1]

    get_courier_id = (sql.SQL(
        "SELECT c.courier_id FROM courier c JOIN users u ON c.user_id = u.user_id WHERE u.user_tgchat_id = {} AND u.user_role = 'courier'"
    ))
    try:
        with connect.cursor() as cur:
            courier_id = cur.execute(get_courier_id.format(callback.message.chat.id)).fetchone()[0]
    except ps.Error as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")

    try:
        with connect.cursor() as cur:
            order_status = cur.execute(
                "SELECT order_status FROM \"order\" WHERE order_id = {} FOR UPDATE NOWAIT;".format(
                    order_id)).fetchone()[0]
            if order_status is None or order_status != 0:
                await callback.answer("Невозможно принять этот заказ!")
                connect.rollback()
                return
            cur.execute("INSERT INTO delivery (courier_id, order_id) VALUES ({}, {});".format(courier_id, order_id))
            cur.execute(
                "UPDATE courier SET courier_is_busy_with_order = true WHERE courier_id = {};".format(courier_id))
            cur.execute("UPDATE \"order\" SET order_status = 1 WHERE order_id = {};".format(order_id))
            connect.commit()
            await Database.notify_channel("order_status", f'action: order_accept; order_id: {order_id}')
            await callback.answer()
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