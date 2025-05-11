import asyncio

from bot import setup_bot
from handlers.deliveries import get_free_couriers
from logger import setup_logger
from notify import setup_notifications


async def main():
    setup_logger()
    await setup_notifications()
    await setup_bot()


if __name__ == "__main__":
    asyncio.run(main())
