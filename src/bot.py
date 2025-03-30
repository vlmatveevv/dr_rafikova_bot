import asyncio
import json
import locale
import logging
import traceback
import html
import re
import time as time_new
from datetime import time, datetime, timedelta
from pathlib import Path

import pytz
import telegram
from setup import pdb
import config
import yaml
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, BotCommand, ReplyKeyboardMarkup, \
    ReplyKeyboardRemove, KeyboardButton, InputMediaPhoto, InputMediaDocument
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    CallbackContext,
    MessageHandler,
    TypeHandler,
    JobQueue,
    AIORateLimiter,
    filters)

# Установка русской локали
locale.setlocale(locale.LC_TIME, ('ru_RU', 'UTF-8'))

# Установка часового пояса МСК
moscow_tz = pytz.timezone('Europe/Moscow')


# Функция для форматирования времени в логах
def custom_time(*args):
    utc_dt = pytz.utc.localize(datetime.utcnow())
    converted = utc_dt.astimezone(moscow_tz)
    return converted.timetuple()


# Настройка формата и уровня логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.Formatter.converter = custom_time
# Создание логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Получите логгер для модуля 'httpx'
logger_for_httpx = logging.getLogger('httpx')
# Установите уровень логирования на WARNING, чтобы скрыть INFO и DEBUG сообщения
logger_for_httpx.setLevel(logging.WARNING)


async def user_exists_pdb(user_id: int) -> bool:
    return pdb.user_exists(user_id)


async def register(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""
    username = update.effective_chat.username or ""
    # Добавление информации о пользователе в базу данных
    if not await user_exists_pdb(user_id):
        pdb.add_user(user_id, username, first_name, last_name)

    keyboard = [[InlineKeyboardButton(config.bot_btn['buy_courses'], callback_data='buy_courses')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # Отправляем сообщение вместе с кнопкой
    await context.bot.send_message(chat_id=user_id,
                                   text=f"Hello, {first_name}",
                                   reply_markup=reply_markup,
                                   parse_mode=ParseMode.HTML)


async def buy_courses_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = []
    for key, course in config.courses.items():
        num_of_chapter = key.split('_')[1]  # Например, "1" из "ch_1"
        button_text = course['name']  # Название из YAML: "1. ПОДГОТОВКА И ПЛАНИРОВАНИЕ БЕРЕМЕННОСТИ"
        button = InlineKeyboardButton(
            text=button_text,
            callback_data=f'buy_chapter:{num_of_chapter}'
        )
        keyboard.append([button])  # Каждая кнопка на отдельной строке

    # Создаем клавиатуру
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение
    await query.edit_message_text(
        text=config.bot_msg['choose_chapter'],
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def buy_chapter_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    # Получаем номер раздела из callback_data
    num_of_chapter = query.data.split(':')[1]

    # Получаем информацию о курсе
    chapter_key = f'ch_{num_of_chapter}'
    course = config.courses['courses'].get(chapter_key)

    if not course:
        await query.edit_message_text("Раздел не найден.")
        return

    # Формируем текст сообщения
    text = config.bot_msg['buy_chapter_info'].format(
        description=course['description'],
        price=course['price'],
        name=course['name']
    )

    # Создаем кнопки
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить", callback_data=f'pay_chapter:{num_of_chapter}')],
        [InlineKeyboardButton("🔙 Назад", callback_data='buy_courses')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


def run():
    # Создание экземпляра RateLimiter
    rate_limiter = AIORateLimiter(
        overall_max_rate=30,  # Максимум 30 сообщений в секунду на всего бота
        overall_time_period=1,  # Временной период для общего лимита (в секундах)
        group_max_rate=20,  # Максимум 20 сообщений в минуту на группу
        group_time_period=60  # Временной период для группового лимита (в секундах)
    )

    application = (
        ApplicationBuilder()
        .token(config.config_env['TELEGRAM_TOKEN'])
        .read_timeout(60)
        .write_timeout(60)
        .concurrent_updates(True)
        .rate_limiter(rate_limiter)
        .build()
    )

    application.add_handler(CommandHandler('start', register))
    application.add_handler(CallbackQueryHandler(buy_courses_callback_handle, pattern="^buy_courses$"))
    application.add_handler(CallbackQueryHandler(buy_chapter_callback_handle(), pattern="^buy_chapter:"))

    logger.addHandler(logging.StreamHandler())

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    run()
