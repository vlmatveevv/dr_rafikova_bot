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
    # Отправляем сообщение вместе с кнопкой
    await context.bot.send_message(chat_id=user_id,
                                   text=f"Hello, {first_name}",
                                   parse_mode=ParseMode.HTML)


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

    logger.addHandler(logging.StreamHandler())

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    run()
