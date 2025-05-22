from handlers.deliveries import get_notify, low_rating
from .database import Database


async def setup_notifications():
    await Database.listen_channel("create_order", get_notify)
    await Database.listen_channel("low_rating", low_rating)
