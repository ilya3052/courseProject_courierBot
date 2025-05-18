from .database import Database
from handlers.deliveries import get_notify


async def setup_notifications():
    await Database.listen_channel("create_order", get_notify)
