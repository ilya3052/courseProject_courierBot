from handlers.channels_func import get_notify, low_rating
from .database import db


async def setup_notifications():
    await db.listen_channel("create_order", get_notify)
    await db.listen_channel("low_rating", low_rating)
