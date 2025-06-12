import logging
from datetime import datetime as dt
from decimal import Decimal

import psycopg as ps
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from asyncpg import PostgresError
from icecream import ic
from psycopg import sql

from Filters.IsRegistered import IsRegistered
from core.database import Database, db
from keyboards import get_profile_kb, get_deliveries_kb
from .register import cmd_start

router = Router()
quantize = Decimal('.01')
page_size = 10


class ProfileState(StatesGroup):
    show_profile = State()
    show_deliveries = State()


@router.message(Command("profile"), IsRegistered())
async def profile_handler(message: Message, state: FSMContext):
    if state != ProfileState.show_profile:
        await state.set_state(ProfileState.show_profile)
    msg, courier_id = await get_courier_info(message.chat.id)
    await state.set_state(ProfileState.show_profile)
    await state.update_data(courier_id=courier_id)
    await message.answer(text=msg, reply_markup=get_profile_kb())


@router.callback_query(F.data.startswith("action_"), StateFilter(ProfileState.show_profile), IsRegistered())
async def actions_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("page", 0)
    deliveries = data.get("deliveries", [])
    max_page = max((len(deliveries) - 1) // page_size, 0)
    match callback.data.split("_")[1]:
        case "back":
            if page > 0:
                page -= 1
        case "next":
            if page < max_page:
                page += 1
    await show_deliveries(callback, state, page)


@router.message(~IsRegistered())
@router.callback_query(~IsRegistered())
async def reg_handler(update: Message | CallbackQuery, state: FSMContext):
    message = update.message if isinstance(update, CallbackQuery) else update
    await cmd_start(message, state)


async def show_deliveries(callback: CallbackQuery, state: FSMContext, page: int = 0):

    data = await state.get_data()
    courier_id = data.get('courier_id')
    get_deliveries_list = """SELECT delivery.delivery_id, o.order_status, COUNT(a.product_article), 
            CASE WHEN o.order_status = 2 THEN delivery.delivery_rating::VARCHAR ELSE 'Доставка не завершена' END AS rating 
            FROM delivery delivery JOIN "order" o ON delivery.order_id = o.order_id 
            JOIN added a ON o.order_id = a.order_id WHERE delivery.courier_id = $1
            GROUP BY delivery.delivery_id, o.order_status
            ORDER BY delivery.delivery_rating;"""
    try:
        deliveries_list = await db.execute(get_deliveries_list, courier_id, fetch=True)
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
        return

    total = len(deliveries_list)
    max_page = max((total - 1) // page_size, 0)
    start = page * page_size
    end = start + page_size
    page_data = deliveries_list[start:end]

    if not page_data:
        await callback.message.edit_text("Нет доставок для отображения.")
        return

    msg_lines = [
        f"Доставка №{delivery['delivery_id']}\n"
        f"\t\tСтатус: {("В пути" if delivery['order_status'] == 1 else "Доставлена получателю")}\n"
        f"\t\tКоличество товаров: {delivery['count']}"
        f"{f"\n\t\tОценка: {delivery['rating']}" if delivery['order_status'] == 2 else ""}"
        for delivery in page_data
    ]
    msg_text = "\n\n".join(msg_lines)

    await state.update_data(page=page, deliveries=deliveries_list)

    try:
        await callback.message.edit_text(
            text=f"Ваши доставки (стр. {page + 1}/{max_page + 1}):\n\n{msg_text}",
            reply_markup=get_deliveries_kb()
        )
    except TelegramBadRequest as TBR:
        logging.exception(f"Произошла ошибка при выполнении запроса {TBR}")
    await callback.answer()


async def get_courier_info(tgchat_id: int) -> (str, int):

    get_courier_id = "SELECT courier_id FROM courier c JOIN users u ON c.user_id = u.user_id WHERE u.user_tgchat_id = $1"

    get_courier_name = "SELECT user_name FROM users WHERE user_tgchat_id = $1 AND user_role = 'courier';"

    get_finished_order_count = "SELECT COUNT(*) FROM \"order\" o JOIN delivery d on o.order_id = d.order_id WHERE d.courier_id = $1 AND o.order_status = 2;"

    get_courier_rating = "SELECT courier_rating FROM courier WHERE courier_id = $1;"

    get_current_order_number = "SELECT d.delivery_id FROM delivery d JOIN \"order\" o ON d.order_id = o.order_id WHERE o.order_status = 1 AND d.courier_id = $1"

    try:
        courier_id = await db.execute(get_courier_id, tgchat_id, fetchval=True)
        courier_name = await db.execute(get_courier_name, tgchat_id, fetchval=True)
        courier_rating = await db.execute(get_courier_rating, courier_id, fetchval=True)

        finished_order_count = await db.execute(get_finished_order_count, courier_id, fetchval=True)
        current_order_number = await db.execute(get_current_order_number, courier_id, fetchval=True)
    except PostgresError as p:
        logging.info(f"Произошла ошибка при выполнении запроса: {p}")
        return

    time = dt.now().hour
    greeting = (
        "Доброй ночи" if 0 <= time < 6 else
        "Доброе утро" if 6 <= time < 12 else
        "Добрый день" if 12 <= time < 18 else
        "Добрый вечер"
    )

    advice = (
        "Все замечательно!" if int(courier_rating) == 5 else
        "Все хорошо!" if 4.60 <= round(courier_rating, 2) < 5.00 else
        "Обратите внимание!" if 4.10 <= round(courier_rating, 2) < 4.60 else
        "Доступ к новым заказам временно ограничен! Обратитесь к администратору"
    )

    hello_message = (f"👋🏼 {greeting}, {courier_name}!\n"
                     f"⭐ Ваш рейтинг: {Decimal(courier_rating).quantize(quantize).normalize()}.\n{advice}\n\n"
                     f"🛒 Общее количество выполненных доставок: {finished_order_count}\n"
                     f"🛒 Текущая доставка: {current_order_number or 'Не назначена'}\n")

    return hello_message, courier_id
