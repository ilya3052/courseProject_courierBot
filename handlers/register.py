import logging
import re

import psycopg as ps
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from psycopg import sql

from core.database import Database

router = Router()


class Register(StatesGroup):
    enter_name = State()
    enter_phonenumber = State()


@router.message(StateFilter(None), Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    connect: ps.connect = Database.get_connection()
    # проверка на существование пользователя
    with connect.cursor() as cur:
        try:
            get_user_id = sql.SQL("SELECT user_id FROM users WHERE user_tgchat_id = %s AND user_role = 'courier'")
            user_id = cur.execute(get_user_id, (message.chat.id,)).fetchone()
        except ps.Error as p:
            await message.answer(f"Произошла ошибка при выполнении запроса: {p}")
            return

    if user_id:
        with connect.cursor() as cur:
            try:
                get_username = sql.SQL(
                    "SELECT user_name FROM users WHERE user_tgchat_id = %s AND user_role = 'courier'")
                username = cur.execute(get_username, (message.chat.id,)).fetchone()[0]
            except ps.Error as p:
                await message.answer(f"Произошла ошибка при выполнении запроса: {p}")
                return
        await message.answer(f"Добро пожаловать, {username}!")
        return

    # проверка на валидность ссылки
    with connect.cursor() as cur:
        try:
            get_chat_id = sql.SQL("SELECT 1 FROM users WHERE user_tgchat_id = %s AND user_role = 'courier'")
            is_link_valid = cur.execute(get_chat_id, (message.text.split()[1]), ).fetchone()
        except ps.Error as p:
            await message.answer(f"Произошла ошибка при выполнении запроса: {p}")
            return

    if is_link_valid is None:
        await message.answer("Ссылка недействительна, пожалуйста, получите действующую у администратора")
    else:
        await message.answer("Введите имя в формате ФИО (отчество при наличии)")
        await state.set_state(Register.enter_name)
        await state.update_data(chat_id_stub=message.text.split()[1])
        await state.update_data(chat_id=message.chat.id)
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
        if insert_data(data):
            logging.info("Регистрация завершена")
            await message.answer(f"Регистрация завершена. Можете приступать к работе.")
        else:
            await message.answer("Регистрация не завершена, попробуйте еще раз получив у администратора новую ссылку!")
    else:
        await message.answer("Неправильный формат ввода, попробуйте еще раз!")


def insert_data(data: dict) -> bool:
    connect: ps.connect = Database.get_connection()
    data['phonenumber'] = (data['phonenumber'].replace('(', '')
                           .replace(')', '')
                           .replace('-', '')
                           .replace('+', ''))
    update_user = (sql.SQL(
        """UPDATE users 
            SET user_tgchat_id = %s, user_name = %s, user_surname = %s, user_patronymic = %s, user_phonenumber = %s 
            WHERE user_tgchat_id = %s
            RETURNING user_id;"""
    ))
    insert_courier = (sql.SQL(
        "INSERT INTO courier (user_id) VALUES (%s);"
    ))
    with connect.cursor() as cur:
        try:
            cur.execute(
                update_user, (
                    data['chat_id'], data['name'][1], data['name'][0],
                    data['name'][2] if len(data['name']) > 2 else None, data['phonenumber'], data['chat_id_stub'],
                ))
            user_id = cur.fetchone()[0]
            cur.execute(insert_courier, (
                user_id,
            ))
            connect.commit()
            logging.info("Запрос выполнен")
            return True
        except ps.Error as e:
            connect.rollback()
            logging.critical(f"Запрос не выполнен. {e}")
        except Exception as e:
            connect.rollback()
            logging.exception(f"При выполнении запроса произошла ошибка: {e}")
            return False
