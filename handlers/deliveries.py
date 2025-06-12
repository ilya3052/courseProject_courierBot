import logging

import psycopg as ps
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from asyncpg import PostgresError
from icecream import ic
from psycopg import sql
from psycopg.errors import LockNotAvailable

from Filters.IsRegistered import IsRegistered
from core.bot_instance import bot
from core.database import Database, db
from keyboards import get_order_notify_kb
from .register import cmd_start

router = Router()


class Deliveries(StatesGroup):
    confirm = State()


@router.callback_query(F.data.startswith("action_accept"), IsRegistered())
async def order_accept_handler(callback: CallbackQuery):

    order_id = callback.data.split(":")[1]

    try:
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                status = await db.execute("SELECT accept_order($1, $2)", callback.message.chat.id, order_id, fetchval=True)
                if status == 1:
                    raise LockNotAvailable()
                await callback.answer()
                await db.notify_channel("order_status", f'action: order_accept; order_id: {order_id}')
    except LockNotAvailable:
        await callback.answer("Заказ уже принят другим курьером!")

    await callback.answer()


@router.callback_query(F.data.startswith("action_cancel"), IsRegistered())
async def order_cancel_handler(callback: CallbackQuery):
    await callback.message.delete()


@router.message(~IsRegistered())
@router.callback_query(~IsRegistered())
async def reg_handler(update: Message | CallbackQuery, state: FSMContext):
    message = update.message if isinstance(update, CallbackQuery) else update
    await cmd_start(message, state)


async def send_notify(order_id: int):

    free_couriers = await get_free_couriers()

    if not free_couriers:
        await db.notify_channel("order_status", f"action: order_not_accept; order_id: {order_id}")
        return

    get_product_info ="""SELECT COUNT(*), o.order_address 
FROM \"order\" o 
    JOIN added a on o.order_id = a.order_id 
    WHERE o.order_id = $1
GROUP BY o.order_address;"""

    get_product_list = """SELECT DISTINCT p.product_name, COUNT(p.product_name), p.product_price 
FROM product p 
	JOIN added a on a.product_article = p.product_article 
	JOIN "order" o ON o.order_id = a.order_id 
WHERE o.order_id = $1
GROUP BY p.product_name, p.product_price;
        """

    get_product_total_price = """SELECT SUM(p.product_price) 
FROM product p 
    JOIN added a ON a.product_article = p.product_article 
    JOIN \"order\" o ON o.order_id = a.order_id 
WHERE o.order_id = $1;"""

    try:
        product_info = await db.execute(get_product_info, order_id, fetchrow=True)
        product_total_price = await db.execute(get_product_total_price, order_id, fetchval=True)
        products_list = await db.execute(get_product_list, order_id, fetch=True)
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
        return

    order_desc = "Список товаров:\n"

    for item in products_list:
        order_desc += f"{item['product_name']} - {item['count']} шт., {item['product_price']} за шт.\n"

    for courier in free_couriers:
        await bot.send_message(chat_id=courier,
                               text=f'Получен новый заказ!\n'
                                    f'Количество товаров - {product_info['count']}\n'
                                    f'Адрес доставки - {product_info['order_address']}\n'
                                    f'Сумма заказа - {product_total_price}\n{order_desc}',
                               reply_markup=get_order_notify_kb(order_id))


async def get_free_couriers() -> None | list:
    try:
        free_couriers = await db.execute(
            """SELECT u.user_tgchat_id 
                    FROM courier c 
                    JOIN users u ON c.user_id = u.user_id 
                WHERE c.courier_is_busy_with_order = false AND u.user_role = 'courier';""", fetch=True)
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
        return None

    free_couriers = [courier[0] for courier in free_couriers]
    return free_couriers
