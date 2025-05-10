from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_deliveries_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="action_back")
    builder.button(text="Далее", callback_data="action_next")
    builder.adjust(2)

    return builder.as_markup()