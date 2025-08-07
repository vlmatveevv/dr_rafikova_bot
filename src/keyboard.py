from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config


def main_menu_button_markup():
    keyboard = [[InlineKeyboardButton(
        text=config.bot_btn['main_menu_main'],
        callback_data='main_menu'
    )]]
    return keyboard


def buy_multiply_button_markup():
    keyboard = [[InlineKeyboardButton(
        text=config.bot_btn['buy_multiply']['main'],
        callback_data='buy_multiply'
    )]]
    return keyboard


def ch_choose_button(available_courses=None, mode='buy', selected=None, menu_path='def'):
    keyboard = []

    # Теперь у нас только один курс
    course_key = 'course'
    course = config.courses.get(course_key)
    
    if course:
        name = course['short_name'] + course['emoji']

        # Добавляем галочку, если в режиме multi_buy и курс выбран
        if mode == 'multi_buy' and course_key in (selected or []):
            name = '✅ ' + name

        button = InlineKeyboardButton(
            text=name,
            callback_data=f'{mode}_chapter:{menu_path}'
        )
        keyboard.append([button])

    return keyboard


def main_menu_items_button_markup():
    main_menu = config.bot_btn['main_menu']

    # Каждая кнопка — это (название, callback_data)
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=key)]
        for key, label in main_menu.items()
    ]

    return InlineKeyboardMarkup(buttons)


def buy_multiply_menu_items_button():
    buy_multiply_menu = config.bot_btn['buy_multiply']['menu']

    # Каждая кнопка — это (название, callback_data)
    buttons = [
        [InlineKeyboardButton(text=label, callback_data=f'{key}_buy_multiply')]
        for key, label in buy_multiply_menu.items()
    ]

    return buttons


def renew_subscription_button_markup():
    """
    Кнопка для оформления подписки заново.
    Используется при неудачных попытках списания.
    """
    keyboard = [[InlineKeyboardButton(
        text=config.bot_btn['renew_subscription'],
        callback_data='pay_chapter'
    )]]
    return InlineKeyboardMarkup(keyboard)
