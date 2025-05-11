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
        text=config.bot_btn['buy_multiply'],
        callback_data='buy_multiply'
    )]]
    return keyboard

#
# def ch_choose_button(available_courses=None):
#     chapter_order = ['ch_7', 'ch_1', 'ch_2', 'ch_3', 'ch_4', 'ch_5', 'ch_6']
#     keyboard = []
#
#     for key in chapter_order:
#         if available_courses is None or key in available_courses:
#             course = config.courses[key]
#             num_of_chapter = key.split('_')[1]
#             button = InlineKeyboardButton(
#                 text=course['short_name'] + course['emoji'],
#                 callback_data=f'buy_chapter:{num_of_chapter}'
#             )
#             keyboard.append([button])
#
#     return keyboard


def ch_choose_button(available_courses=None, mode='buy', selected=None):
    chapter_order = ['ch_7', 'ch_1', 'ch_2', 'ch_3', 'ch_4', 'ch_5', 'ch_6']
    keyboard = []

    selected = selected or []

    for key in chapter_order:
        if available_courses is None or key in available_courses:
            course = config.courses[key]
            num_of_chapter = key.split('_')[1]
            name = course['short_name'] + course['emoji']

            # Добавляем галочку, если в режиме multi_buy и глава выбрана
            if mode == 'multi_buy' and key in selected:
                name = '✅ ' + name

            button = InlineKeyboardButton(
                text=name,
                callback_data=f'{mode}_chapter:{num_of_chapter}'  # например: multi_buy_chapter:1
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