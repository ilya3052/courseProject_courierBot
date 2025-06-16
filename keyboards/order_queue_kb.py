from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_order_queue_kb(orders: list[int]):
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.button(text=f"{order}", callback_data=f"queue_order_{order}")

    static_builder = InlineKeyboardBuilder()
    static_builder.button(text="Вернуться назад ↩️️", callback_data="queue_action_back")

    builder.adjust(2)
    builder.attach(static_builder)

    return builder.as_markup()
