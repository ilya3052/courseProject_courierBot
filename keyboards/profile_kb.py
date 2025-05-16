from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Доставки", callback_data="action_deliveries")

    return builder.as_markup()
