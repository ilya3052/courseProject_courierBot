from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_order_notify_kb(order_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять заказ", callback_data=f"action_accept:{order_id}")
    builder.button(text="❌ Отказаться от заказа", callback_data="action_cancel")

    return builder.as_markup()