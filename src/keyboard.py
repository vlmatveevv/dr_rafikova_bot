from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config


def main_menu_button_markup():
    main_menu = config.bot_btn['main_menu']

    # Каждая кнопка — это (название, callback_data)
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=key)]
        for key, label in main_menu.items()
    ]

    return InlineKeyboardMarkup(buttons)