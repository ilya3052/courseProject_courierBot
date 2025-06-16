import logging
from datetime import datetime as dt
from decimal import Decimal

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asyncpg import PostgresError
from icecream import ic

from Filters.IsRegistered import IsRegistered
from core.database import db
from keyboards import get_profile_kb, get_deliveries_kb
from keyboards.order_queue_kb import get_order_queue_kb
from .register import cmd_start

router = Router()
quantize = Decimal('.01')
page_size = 10


class ProfileState(StatesGroup):
    show_profile = State()
    show_deliveries = State()
    show_orderQueue = State()


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
    match callback.data.split("_")[1]:
        case "deliveries":
            await state.set_state(ProfileState.show_deliveries)
            await show_deliveries(callback, state)
        case "orderQueue":
            await state.set_state(ProfileState.show_orderQueue)
            await show_order_queue(callback, state)


@router.callback_query(F.data.startswith("action_"), StateFilter(ProfileState.show_deliveries), IsRegistered())
async def deliveries_actions(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get('page', 0)
    deliveries = data.get('deliveries', [])
    total = len(deliveries)
    max_page = max((total - 1) // page_size, 0)
    match callback.data.split("_")[1]:
        case "back":
            if page > 0:
                page -= 1
        case "next":
            if page < max_page:
                page += 1
    await show_deliveries(callback, state, page)


@router.callback_query(F.data.startswith("queue_"), StateFilter(ProfileState.show_orderQueue), IsRegistered())
async def queue_handler(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split("queue_")[1]
    match action.split("_")[0]:
        case "action":
            await show_profile(callback, state)
        case "order":
            order_id = action.split("_")[1]
            await state.update_data(order_id=order_id)
            await show_order(callback, state)


@router.callback_query(F.data.startswith("order_").StateFilter(ProfileState.show_orderQueue), IsRegistered())
async def show_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = int(data.get('order_id'))
    get_order_info = """SELECT o.order_id, u.user_surname, u.user_name, u.user_phonenumber, p.product_article, COUNT(p.product_article), p.product_name, p.product_price, o.order_address, SUM(p.product_price) 
        FROM "order" o 
            JOIN added a ON o.order_id = a.order_id 
            JOIN product p ON a.product_article = p.product_article 
            JOIN delivery d ON o.order_id = d.order_id
            JOIN client c ON c.client_id = o.client_id
            JOIN users u ON c.user_id = u.user_id
        WHERE o.order_id = $1
        GROUP BY o.order_id, u.user_surname, u.user_name, p.product_article, u.user_phonenumber"""

    try:
        order_info = await db.execute(get_order_info, order_id, fetch=True)
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
        return

    msg = (f"Информация о заказе №{order_info[0]['order_id']}\n"
           f"Получатель - {order_info[0]['user_surname']} {order_info[0]['user_name']}\n"
           f"Телефон для свзяи - {order_info[0]['user_phonenumber']}\n"
           f"Адрес доставки - {order_info[0]['order_address']}\n"
           f"Общая сумма заказа - {order_info[0]['sum']}\n"
           f"Список товаров\n")

    for item in order_info:
        msg += (f"{item['product_name']} ({item['product_article']}) "
                f"в количестве {item['count']} шт., {item['product_price']}₽ за шт.\n")

    await state.set_state(ProfileState.show_profile)
    await callback.message.edit_text(text=msg,
                                     reply_markup=InlineKeyboardMarkup(
                                         inline_keyboard=[[InlineKeyboardButton(text="Вернуться назад",
                                                                                callback_data="action_orderQueue")]]
                                     ))


@router.message(~IsRegistered())
@router.callback_query(~IsRegistered())
async def reg_handler(update: Message | CallbackQuery, state: FSMContext):
    message = update.message if isinstance(update, CallbackQuery) else update
    await cmd_start(message, state)


async def show_deliveries(callback: CallbackQuery, state: FSMContext, page: int = 0):
    data = await state.get_data()
    courier_id = data.get('courier_id')
    get_deliveries_list = """SELECT d.delivery_id, o.order_status, COUNT(a.product_article), 
            CASE WHEN o.order_status = 2 THEN d.delivery_rating::VARCHAR ELSE 'Доставка не завершена' END AS rating 
            FROM delivery d JOIN "order" o ON d.order_id = o.order_id 
            JOIN added a ON o.order_id = a.order_id WHERE d.courier_id = $1
            GROUP BY d.delivery_id, o.order_status
            ORDER BY d.delivery_rating;"""
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
        f"Доставка №{deliveries_list['delivery_id']}\n"
        f"\t\tСтатус: {("В пути" if deliveries_list['order_status'] == 1 else "Доставлена получателю")}\n"
        f"\t\tКоличество товаров: {deliveries_list['count']}"
        f"{f"\n\t\tОценка: {deliveries_list['rating']}" if deliveries_list['order_status'] == 2 else ""}"
        for deliveries_list in page_data
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


async def show_order_queue(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    courier_id = data.get('courier_id')

    get_order_count = "SELECT COUNT(delivery_id) FROM order_queue WHERE courier_id = $1;"

    get_current_order = "SELECT delivery_id FROM order_queue WHERE queue_number = 1 AND courier_id = $1;"

    get_orders_from_queue = "SELECT delivery_id FROM order_queue WHERE courier_id = $1 ORDER BY queue_number;"

    try:
        order_count = await db.execute(get_order_count, courier_id, fetchval=True)
        current_order = await db.execute(get_current_order, courier_id, fetchval=True)
        orders_list = await db.execute(get_orders_from_queue, courier_id, fetch=True)
    except PostgresError as p:
        logging.info(f"Произошла ошибка при выполнении запроса: {p}")
        return

    msg = f"Текущий заказ - {current_order}\nЗаказов в очереди - {order_count - 1}\n"

    await callback.message.edit_text(text=msg,
                                     reply_markup=get_order_queue_kb([order['delivery_id'] for order in orders_list]))


async def show_profile(callback: CallbackQuery, state: FSMContext):
    msg, courier_id = await get_courier_info(callback.message.chat.id)
    await state.set_state(ProfileState.show_profile)
    await state.update_data(courier_id=courier_id)
    await callback.message.edit_text(text=msg, reply_markup=get_profile_kb())
