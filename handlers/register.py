import logging
import re

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from asyncpg import PostgresError

from core.database import db

router = Router()


class Register(StatesGroup):
    enter_name = State()
    enter_phonenumber = State()


@router.message(StateFilter(None), Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    get_user_id = "SELECT user_id FROM users WHERE user_tgchat_id = $1 AND user_role = 'courier'"
    try:
        user_id = await db.execute(get_user_id, message.chat.id, fetchval=True)
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
        return

    if user_id:
        try:
            get_username = "SELECT user_name FROM users WHERE user_tgchat_id = $1 AND user_role = 'courier'"
            username = await db.execute(get_username, message.chat.id, fetchval=True)
        except PostgresError as p:
            logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
            return
        await message.answer(f"Добро пожаловать, {username}!")
        return

    try:
        get_chat_id = "SELECT 1 FROM users WHERE user_tgchat_id = $1 AND user_role = 'courier'"
        is_link_valid = await db.execute(get_chat_id, int(message.text.split()[1]), fetchval=True)
    except PostgresError as p:
        logging.exception(f"Произошла ошибка при выполнении запроса: {p}")
        return

    if is_link_valid is None:
        await message.answer("Ссылка недействительна, пожалуйста, получите действующую у администратора")
    else:
        await message.answer("Введите имя в формате ФИО (отчество при наличии)")
        await state.set_state(Register.enter_name)
        await state.update_data(chat_id_stub=message.text.split()[1], chat_id=message.chat.id,
                                username=message.from_user.username)
        logging.info("Введено имя")


@router.message(Register.enter_name)
async def enter_nickname(message: Message, state: FSMContext):
    await message.answer("Укажите номер телефона в формате +7(***)***-**-**")
    await state.update_data(name=message.text.split())
    await state.set_state(Register.enter_phonenumber)
    logging.info("Номер телефона введен")


@router.message(Register.enter_phonenumber)
async def enter_phonenumber(message: Message, state: FSMContext):
    pattern = re.compile(r'^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$')
    if pattern.match(message.text):
        await state.update_data(phonenumber=message.text)
        data = await state.get_data()
        await state.clear()
        if await insert_data(data):
            logging.info("Регистрация завершена")
            await message.answer(f"Регистрация завершена. Можете приступать к работе.")
            await db.notify_channel('courier_is_registered', '')
        else:
            await message.answer("Регистрация не завершена, попробуйте еще раз получив у администратора новую ссылку!")
    else:
        await message.answer("Неправильный формат ввода, попробуйте еще раз!")


async def insert_data(data: dict) -> bool:
    data['phonenumber'] = (data['phonenumber'].replace('(', '')
                           .replace(')', '')
                           .replace('-', '')
                           .replace('+', ''))
    update_user = """UPDATE users 
            SET user_tgchat_id = $1, user_name = $2, user_surname = $3, user_patronymic = $4, user_phonenumber = $5, user_tg_username = $6 
            WHERE user_tgchat_id = $7
            RETURNING user_id;"""
    insert_courier = "INSERT INTO courier (user_id) VALUES ($1);"
    try:
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                user_id = await db.execute(
                    update_user,
                    data['chat_id'], data['name'][1], data['name'][0],
                    data['name'][2] if len(data['name']) > 2 else None, data['phonenumber'], data['username'],
                    int(data['chat_id_stub']), fetchval=True
                )
                await db.execute(insert_courier, user_id, execute=True)
                logging.info("Запрос выполнен")
                return True
    except PostgresError as e:
        logging.critical(f"Запрос не выполнен. {e}")
        return False
    except Exception as e:
        logging.exception(f"При выполнении запроса произошла ошибка: {e}")
        return False
