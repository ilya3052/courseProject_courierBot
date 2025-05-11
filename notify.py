from database import Database
from handlers.deliveries import get_free_couriers


async def get_notify(conn, pid, channel, payload):
    order_id = str(payload).split(":")[1].strip()
    print(f"[{channel}] => {payload} => {order_id}")
    await get_free_couriers()


async def setup_notifications():
    await Database.listen_channel("create_order", get_notify)