import asyncio
import logging
import os
import psycopg as ps
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from psycopg import AsyncConnection
from handlers import profile_router, reg_router
from shared.database import Database

# Путь к файлу для логов
log_path = os.path.join(os.path.dirname(__file__), "logs/couriers_bot_logs.log")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    filename=log_path,
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="UTF-8"
)

# Создание объекта бота
bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

# Логирование запуска бота
logging.info("Бот запущен")

# Диспетчер для обработки маршрутов
dp = Dispatcher()
dp.include_router(reg_router)
dp.include_router(profile_router)

# Функция для прослушивания уведомлений через LISTEN
async def listen_notifications():
    async_connect = await Database.get_async_connection()
    if not async_connect:
        logging.error("Не удалось установить асинхронное соединение!")
        return

    await async_connect.execute("LISTEN create_order;")
    logging.info("🔔 Listening on 'create_order' channel...")

    async for notify in async_connect.notifies():
        logging.info(f"📨 Received: {notify.channel} - {notify.payload}")
        # Здесь можно обработать полученные уведомления (например, отправить сообщение)

# Функция для обработки обновлений бота (start_polling)
async def start_polling():
    logging.info("Запущен бот для обработки обновлений...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

# Основная функция для запуска всех задач
async def main():
    # Запуск двух задач параллельно
    await asyncio.gather(start_polling(), listen_notifications())

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Запуск асинхронного приложения
    asyncio.run(main())
