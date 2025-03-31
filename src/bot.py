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

ASK_EMAIL = 1


async def user_exists_pdb(user_id: int) -> bool:
    return pdb.user_exists(user_id)


async def register(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""
    username = update.effective_chat.username or ""

    # Добавление пользователя в БД
    if not await user_exists_pdb(user_id):
        pdb.add_user(user_id, username, first_name, last_name)

    keyboard = [[InlineKeyboardButton(config.bot_btn['buy_courses'], callback_data='buy_courses')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=user_id,
        text=f"Hello, {first_name}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


# Покупка курсов (список)
async def buy_courses_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    keyboard = []

    for key, course in config.courses.items():
        num_of_chapter = key.split('_')[1]
        button = InlineKeyboardButton(
            text=course['name'],
            callback_data=f'buy_chapter:{num_of_chapter}'
        )
        keyboard.append([button])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=config.bot_msg['choose_chapter'],
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


# Детали конкретного курса
async def buy_chapter_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    num_of_chapter = query.data.split(':')[1]
    course = config.courses.get(f'ch_{num_of_chapter}')

    if not course:
        await query.edit_message_text("Раздел не найден.")
        return

    text = config.bot_msg['buy_chapter_info'].format(
        description=course['description'],
        price=course['price'],
        name=course['name']
    )

    keyboard = [
        [InlineKeyboardButton(config.bot_btn['go_to_pay'], callback_data=f'pay_chapter:{num_of_chapter}')],
        [InlineKeyboardButton(config.bot_btn['go_back'], callback_data='buy_courses')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )


# Переход к оплате
async def pay_chapter_callback_handle(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    # Не даём пользователю начать второй заказ, если первый не завершён
    if context.user_data.get('is_in_conversation'):
        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить и оплатить", url="https://example.com/payment-link")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("У вас есть незавершённый заказ ⛔️", reply_markup=reply_markup)
        return ASK_EMAIL

    num_of_chapter = query.data.split(':')[1]
    course = config.courses.get(f'ch_{num_of_chapter}')

    if not course:
        await query.edit_message_text("Курс не найден.")
        return ConversationHandler.END

    # Сохраняем данные и флаг активности
    context.user_data['selected_course'] = course
    context.user_data['chapter_number'] = num_of_chapter
    context.user_data['is_in_conversation'] = True

    email_msg = await query.edit_message_text("Введите ваш e-mail для отправки чека:")
    context.user_data['email_msg'] = email_msg

    return ASK_EMAIL


# Обработка ввода email
async def ask_email_handle(update: Update, context: CallbackContext) -> int:
    email = update.message.text
    context.user_data['email'] = email
    email_msg = context.user_data['email_msg']
    user_id = update.effective_user.id

    # Удаляем сообщение и e-mail
    try:
        await context.bot.delete_message(chat_id=user_id, message_id=email_msg.message_id)
        await update.message.delete()
    except:
        pass

    course = context.user_data['selected_course']
    num = context.user_data['chapter_number']

    text = config.bot_msg['confirm_purchase'].format(
        email=email,
        name=course['name'],
        num=num,
        price=course['price'],
    )

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и оплатить", url="https://example.com/payment-link")],
        [InlineKeyboardButton("❌ Отмена", callback_data="cancel_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.chat.send_message(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


# Отмена покупки
async def cancel_payment_handle(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    await query.edit_message_text("Покупка отменена.")
    return ConversationHandler.END


# ConversationHandler
buy_course_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(pay_chapter_callback_handle, pattern=r'^pay_chapter:\d+$')],
    states={
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email_handle)],
    },
    fallbacks=[CallbackQueryHandler(cancel_payment_handle, pattern='^cancel_payment$')],
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
    application.add_handler(CallbackQueryHandler(buy_chapter_callback_handle, pattern="^buy_chapter:"))
    application.add_handler(buy_course_conversation)

    logger.addHandler(logging.StreamHandler())

    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    run()
