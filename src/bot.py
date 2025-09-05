import asyncio
import json
import locale
import logging
import traceback
import html
import re
import time as time_new
from datetime import time, datetime, timedelta, timezone
from pathlib import Path

import pytz
import telegram
import other_func
from telegram_func import send_or_edit_message, send_or_edit_photo
from setup import pdb
import config
import yaml
import keyboard as my_keyboard
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
    ChatJoinRequestHandler,
    filters)

import payment
from subscription_jobs import schedule_subscription_jobs, cancel_subscription_jobs, schedule_daily_sync, \
    sync_job_queue_with_db

# Установка русской локали
locale.setlocale(locale.LC_TIME, ('ru_RU', 'UTF-8'))

# Установка часового пояса МСК
moscow_tz = pytz.timezone('Europe/Moscow')

# Это словарь одобренных пользователей
allowed_users = {
    7768888247: "Roman"
}


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

AGREE_OFFER, AGREE_PRIVACY, AGREE_NEWSLETTER, ASK_EMAIL = range(4)


# Обработка ввода email
def is_valid_email(email: str) -> bool:
    # Регулярное выражение для проверки корректности email
    pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(pattern, email) is not None


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

    keyboard = [
        [InlineKeyboardButton(config.bot_btn['buy_courses'], callback_data='pay_chapter')],
        [InlineKeyboardButton(config.bot_btn['test_sub'], callback_data='pay_chapter:test_sub')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = f"{config.bot_msg['hello'].format(first_name=first_name)}"
    video_path = config.media_dir / "video.mp4"

    try:
        with open(video_path, 'rb') as video:
            await context.bot.send_video_note(
                chat_id=user_id,
                video_note=video
            )
    except telegram.error.BadRequest as e:
        logger.info(f"Ошибка при отправке video note: {e}")
        pass

    # Задержка 3 секунды перед отправкой текста
    await asyncio.sleep(3)

    await send_or_edit_message(update, context, caption, reply_markup, True)

    return ConversationHandler.END


async def start_callback_handle(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки start из главного меню"""
    query = update.callback_query
    await query.answer()
    await register(update, context)


async def my_courses_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    # Получаем все доступные курсы
    available_courses = pdb.get_all_user_courses(user_id)
    menu_path = 'my_courses'

    if not available_courses:
        text = "У вас пока нет доступных курсов."

        reply_markup = InlineKeyboardMarkup(my_keyboard.main_menu_button_markup())
        await send_or_edit_message(update, context, text, reply_markup)
        return

    keyboard = my_keyboard.ch_choose_button(available_courses=available_courses, menu_path=menu_path)
    keyboard.extend(my_keyboard.main_menu_button_markup())
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Ваши доступные курсы. Нажмите, чтобы перейти:"
    await send_or_edit_message(update, context, text, reply_markup)


async def my_courses_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await my_courses_command(update, context)


async def all_courses_command(update: Update, context: CallbackContext) -> None:
    keyboard = my_keyboard.ch_choose_button(menu_path='all_courses')

    keyboard.extend(my_keyboard.buy_multiply_button_markup())
    keyboard.extend(my_keyboard.main_menu_button_markup())
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = config.bot_msg['choose_chapter']
    await send_or_edit_message(update, context, text, reply_markup)


async def all_courses_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await all_courses_command(update, context)


async def documents_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id
    person_info_text = config.other_cfg["person_info"]
    offer_text = f'<a href="{config.other_cfg["links"]["offer"]}">Ознакомиться с офертой</a>'
    privacy_text = f'<a href="{config.other_cfg["links"]["privacy"]}">Ознакомиться с политикой обработки персональных данных</a>'
    consent_text = f'<a href="{config.other_cfg["links"]["consent"]}">Ознакомиться с документом на получение рекламной и информационной рассылки</a>'
    text = person_info_text + "\n\n" + offer_text + "\n\n" + privacy_text + "\n\n" + consent_text

    keyboard = [
        [InlineKeyboardButton("📲 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, context, text, reply_markup)


async def documents_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await documents_command(update, context)


async def support_command(update: Update, context: CallbackContext) -> None:
    text = config.bot_msg['support']
    reply_markup = InlineKeyboardMarkup(my_keyboard.main_menu_button_markup())
    await send_or_edit_message(update, context, text, reply_markup)


async def support_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await support_command(update, context)


async def cancel_sub_command(update: Update, context: CallbackContext) -> None:
    user_id = update.effective_user.id

    # Проверяем, есть ли активная подписка
    if not pdb.has_active_subscription(user_id):
        text = "❌ У вас нет активной подписки для отмены."
        await send_or_edit_message(update, context, text)
        return

    text = config.bot_msg['sub']['cancel']
    keyboard = [
        [InlineKeyboardButton(config.bot_btn['sub']['cancel'], callback_data="cancel_sub_confirm")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, context, text, reply_markup)


async def zxc_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    test_ids = [146679674]

    keyboard = [
        [InlineKeyboardButton(config.bot_btn['test_sub'], callback_data="test_sub")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if user_id not in test_ids:
        await update.message.reply_text(text="test", reply_markup=reply_markup)
        return


async def test_sub_callback_handle(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки test_sub для создания тестовой подписки"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Проверяем, что пользователь в списке тестировщиков
    test_ids = [7768888247, 5738018066]
    if user_id not in test_ids:
        await query.answer("❌ У вас нет прав для создания тестовой подписки")
        return
    
    await query.answer()
    
    try:
        # Проверяем, может ли пользователь создать тестовую подписку
        if not pdb.can_create_test_subscription(user_id):
            await query.edit_message_text(
                text=config.bot_msg['test_sub']['not_available_history'],
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📲 Главное меню", callback_data="main_menu")
                ]])
            )
            return
        
        # Проверяем, есть ли уже активная подписка
        if pdb.has_active_subscription(user_id):
            await query.edit_message_text(
                text=config.bot_msg['test_sub']['not_available_active'],
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📲 Главное меню", callback_data="main_menu")
                ]])
            )
            return
        
        # Создаем тестовый заказ
        order_code = other_func.generate_order_number()
        order_id = pdb.create_order(user_id=user_id, order_code=order_code)
        
        # Получаем email пользователя (если есть)
        user_info = pdb.get_user_by_user_id(user_id)
        email = 'ya.matveev116@ya.ru'
        
        # Создаем тестовый платеж
        payment_url = payment.create_test_payment_robokassa(
            email=email,
            order_code=order_code,
            order_id=order_id,
            user_id=user_id
        )
        
        # Создаем клавиатуру с кнопкой оплаты
        keyboard = [
            [InlineKeyboardButton("💳 Оплатить 1 рубль", url=payment_url)],
            [InlineKeyboardButton("🚫 Отмена", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=config.bot_msg['test_sub']['info'],
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка при создании тестовой подписки: {e}")
        await query.edit_message_text(
            text=config.bot_msg['test_sub']['error'],
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📲 Главное меню", callback_data="main_menu")
            ]])
        )


async def sync_jobs_command(update: Update, context: CallbackContext) -> None:
    """Команда для ручной синхронизации job_queue с БД (только для админов)"""
    user_id = update.message.from_user.id

    # Проверяем, является ли пользователь админом
    admin_ids = [146679674]
    if user_id not in admin_ids:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        await sync_job_queue_with_db(context)
        await update.message.reply_text("✅ Синхронизация job_queue с БД завершена!")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при синхронизации: {e}")


async def jobs_list_command(update: Update, context: CallbackContext) -> None:
    """Команда для просмотра задач в job_queue (только для админов)"""
    user_id = update.message.from_user.id

    # Проверяем, является ли пользователь админом
    admin_ids = [146679674]
    if user_id not in admin_ids:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    try:
        jobs = context.job_queue.jobs()

        if not jobs:
            await update.message.reply_text("📋 Очередь задач пуста")
            return

        # Фильтруем только задачи подписок
        subscription_jobs = [job for job in jobs if
                             job.name and (job.name.startswith("charge_") or job.name.startswith("kick_"))]

        if not subscription_jobs:
            await update.message.reply_text("📋 Задач подписок в очереди нет")
            return

        # Формируем сообщение с информацией о задачах
        message = "📋 Задачи в job_queue:\n\n"

        for i, job in enumerate(subscription_jobs, 1):
            job_name = job.name or "Без имени"
            job_data = job.data or {}

            # Извлекаем информацию из данных задачи
            user_id_job = job_data.get('user_id', 'N/A')
            subscription_id = job_data.get('subscription_id', 'N/A')
            order_id = job_data.get('order_id', 'N/A')

            # Форматируем время выполнения
            if hasattr(job, 'next_t'):
                from datetime import datetime, timezone
                next_run = job.next_t

                # Проверяем тип next_t
                if isinstance(next_run, (int, float)):
                    # Если это timestamp
                    next_run = datetime.fromtimestamp(next_run, tz=timezone.utc)
                elif isinstance(next_run, datetime):
                    # Если это уже datetime объект
                    if next_run.tzinfo is None:
                        next_run = next_run.replace(tzinfo=timezone.utc)
                else:
                    next_run = None

                if next_run:
                    next_run_str = next_run.strftime('%d.%m.%Y %H:%M:%S UTC')
                else:
                    next_run_str = "Не определено"
            else:
                next_run_str = "Не определено"

            message += f"🔹 {i}. {job_name}\n"
            message += f"   👤 User ID: {user_id_job}\n"
            message += f"   📋 Subscription ID: {subscription_id}\n"
            if order_id != 'N/A':
                message += f"   🛒 Order ID: {order_id}\n"
            message += f"   ⏰ Следующий запуск: {next_run_str}\n\n"

        # Если сообщение слишком длинное, разбиваем на части
        if len(message) > 3800:
            parts = [message[i:i + 3800] for i in range(0, len(message), 3800)]
            for i, part in enumerate(parts, 1):
                await update.message.reply_text(f"{part}\n\nЧасть {i}/{len(parts)}")
        else:
            await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при получении списка задач: {e}")


async def cancel_sub_confirm_callback(update: Update, context: CallbackContext) -> None:
    text = config.bot_msg['sub']['cancel_confirm']
    keyboard = [
        [
            InlineKeyboardButton(config.bot_btn['sub']['confirm_cancel'], callback_data="cancel_sub_final"),
            InlineKeyboardButton(config.bot_btn['sub']['keep'], callback_data="cancel_sub_keep")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, context, text, reply_markup)


async def cancel_sub_final_callback(update: Update, context: CallbackContext) -> None:
    user_id = update.callback_query.from_user.id

    try:
        # Получаем активную подписку
        subscription = pdb.get_active_subscription(user_id)
        if not subscription:
            text = "❌ Активная подписка не найдена."
            await send_or_edit_message(update, context, text)
            return

        # Отменяем подписку
        pdb.cancel_subscription(subscription['subscription_id'])

        # Отменяем задачи в job_queue
        cancel_subscription_jobs(context, subscription['subscription_id'], user_id)

        text = config.bot_msg['sub']['canceled']
        await send_or_edit_message(update, context, text)

    except Exception as e:
        logger.error(f"❌ Ошибка при отмене подписки: {e}")
        text = "❌ Произошла ошибка при отмене подписки. Попробуйте позже."
        await send_or_edit_message(update, context, text)


async def cancel_sub_keep_callback(update: Update, context: CallbackContext) -> None:
    text = config.bot_msg['sub']['cancel_keep']
    await send_or_edit_message(update, context, text)


async def cancel_sub_menu_callback(update: Update, context: CallbackContext) -> None:
    """Обработчик кнопки отмены подписки из главного меню"""
    # Просто вызываем существующую функцию
    await cancel_sub_command(update, context)


async def main_menu_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    text = "📲 Главное меню"
    reply_markup = my_keyboard.main_menu_items_button_markup()
    await send_or_edit_message(update, context, text, reply_markup)


async def buy_courses_command(update: Update, context: CallbackContext) -> None:
    keyboard = my_keyboard.ch_choose_button(menu_path='default')

    keyboard.extend(my_keyboard.buy_multiply_button_markup())
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = config.bot_msg['choose_chapter']
    await send_or_edit_message(update, context, text, reply_markup)


# Покупка курсов (список)
async def buy_courses_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await buy_courses_command(update, context)


# Детали конкретного курса
async def buy_chapter_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # У нас только один курс
    course_key = 'course'
    try:
        menu_path = query.data.split(':')[1]
    except Exception:
        menu_path = 'default'

    course = config.courses.get(course_key)

    if not course:
        text = "Курс не найден."
        await send_or_edit_message(update, context, text)
        return

    text = config.bot_msg['buy_chapter_info'].format(
        name=course['name'] + course['emoji'],
        description=course['description'],
        price=course['price']
    )

    keyboard = []

    if pdb.has_active_subscription(user_id) or pdb.has_manual_access(user_id, course_key):
        keyboard.append([
            InlineKeyboardButton(config.bot_btn['go_to_channel'], url=course['channel_invite_link'])
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(config.bot_btn['go_to_pay'], callback_data='pay_chapter')
        ])

    keyboard.append([
        InlineKeyboardButton(config.bot_btn['go_back'], callback_data=f'go_back:{menu_path}')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, context, text, reply_markup)


# Переход к оплате
async def pay_chapter_callback_handle(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Проверяем, это тестовая подписка или обычная
    is_test_subscription = False
    if ':' in query.data:
        parts = query.data.split(':')
        if len(parts) > 1 and parts[1] == 'test_sub':
            is_test_subscription = True

    # У нас только один курс
    course_key = 'course'
    course = config.courses.get(course_key)

    if not course:
        text = "Курс не найден."
        await send_or_edit_message(update, context, text)
        return ConversationHandler.END

    # Проверяем, есть ли уже активная подписка
    if pdb.has_active_subscription(user_id):
        text = (
            "У вас уже есть активная подписка! "
            "Если хотите привязать другую карту, сначала отмените текущую подписку."
        )

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(config.bot_btn['sub']['cancel'], callback_data='cancel_sub')]
        ])

        await send_or_edit_message(update, context, text, reply_markup)
        return ConversationHandler.END

    # Для тестовых подписок проверяем права
    if is_test_subscription:
        test_ids = [7768888247, 5738018066]
        if user_id not in test_ids:
            await query.edit_message_text(
                text="❌ У вас нет прав для создания тестовой подписки",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📲 Главное меню", callback_data="main_menu")
                ]])
            )
            return ConversationHandler.END

        # Проверяем, может ли пользователь создать тестовую подписку
        if not pdb.can_create_test_subscription(user_id):
            await query.edit_message_text(
                text=config.bot_msg['test_sub']['not_available_history'],
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📲 Главное меню", callback_data="main_menu")
                ]])
            )
            return ConversationHandler.END

    order_code = other_func.generate_order_number()
    order_id = pdb.create_order(user_id=user_id, order_code=order_code)
    context.user_data['selected_course'] = course
    context.user_data['course_key'] = course_key
    context.user_data['order_id'] = order_id
    context.user_data['order_code'] = order_code
    context.user_data['is_test_subscription'] = is_test_subscription

    context.user_data['is_in_conversation'] = True

    # Убираем дублирование - сообщение будет отправлено в start_payment_handle
    return await start_payment_handle(update, context, [course_key])


async def confirm_multi_buy_handle(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    selected_courses = context.user_data.get("multi_buy_selected", [])
    user_id = query.from_user.id

    if not selected_courses:
        text = "❗️Вы не выбрали ни одного курса."
        await send_or_edit_message(update, context, text)
        return ConversationHandler.END

    context.user_data['is_in_conversation'] = True
    context.user_data['multi_buy_selected'] = selected_courses

    # Переход в общий обработчик запуска оплаты
    return await start_payment_handle(update, context, selected_courses)


async def start_payment_handle(update: Update, context: CallbackContext, selected_courses: list) -> int:
    query = update.callback_query
    user_id = query.from_user.id

    # У нас только один курс
    course_key = 'course'
    
    # Данные заказа уже созданы в pay_chapter_callback_handle
    order_id = context.user_data['order_id']
    order_code = context.user_data['order_code']

    context.user_data['selected_courses'] = [course_key]

    keyboard = [
        [InlineKeyboardButton("✅ Принимаю", callback_data=f"agree_offer:{order_code}")],
        [InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Определяем текст в зависимости от типа подписки
    is_test_subscription = context.user_data.get('is_test_subscription', False)
    if is_test_subscription:
        text = (
            "💳 Пробная подписка оформляется на 2 дня с автоматическим продлением на полную подписку.\n"
            "Ты можешь отменить её в любой момент.\n\n"
            "📄 Я ознакомился и принимаю условия Публичной оферты.\n\n"
            f'<a href="{config.other_cfg["links"]["offer"]}">Открыть оферту</a>'
        )
    else:
        text = (
            "💳 Подписка оформляется на 1 месяц с автоматическим продлением.\n"
            "Ты можешь отменить её в любой момент.\n\n"
            "📄 Я ознакомился и принимаю условия Публичной оферты.\n\n"
            f'<a href="{config.other_cfg["links"]["offer"]}">Открыть оферту</a>'
        )
    
    await send_or_edit_message(update, context, text, reply_markup)
    return AGREE_OFFER


# Шаг 2 — согласие на обработку ПДн
async def handle_offer_agree(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    order_code = query.data.split(':')[1]
    pdb.update_agreed_offer(order_code, True)

    keyboard = [[InlineKeyboardButton("✅ Даю согласие", callback_data=f"agree_privacy:{order_code}")],
                [InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        '🔐 Я даю согласие на обработку моих персональных данных.\n\n'
        f'<a href="{config.other_cfg["links"]["privacy"]}">Политика обработки данных</a>'
    )
    await send_or_edit_message(update, context, text, reply_markup)
    return AGREE_PRIVACY


# Шаг 3 — согласие на рассылку
async def handle_privacy_agree(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    order_code = query.data.split(':')[1]
    pdb.update_agreed_privacy(order_code, True)

    keyboard = [
        [InlineKeyboardButton("✅ Я согласен", callback_data=f"agree_newsletter:{order_code}")],
        [InlineKeyboardButton("❌ Не согласен", callback_data=f"disagree_newsletter:{order_code}")],
        [InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "📬 Я даю согласие на получение рекламной и информационной рассылки.\n\n"
        f'<a href="{config.other_cfg["links"]["consent"]}">Документ о рассылке</a>'
    )
    await send_or_edit_message(update, context, text, reply_markup)
    return AGREE_NEWSLETTER


# Шаг 4 — e-mail
async def handle_newsletter_agree(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()
    agreement_newsletter, order_code = query.data.split(':')
    if agreement_newsletter == 'agree_newsletter':
        agreement_newsletter_bool = True
    else:
        agreement_newsletter_bool = False

    keyboard = [
        [InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📧 Введите ваш e-mail для отправки чека:"
    email_msg = await send_or_edit_message(update, context, text, reply_markup)
    pdb.update_agreed_newsletter(order_code, agreement_newsletter_bool)

    context.user_data['email_msg'] = email_msg
    context.user_data['order_code'] = order_code
    return ASK_EMAIL


# Шаг 5 — обработка e-mail и оплата
async def ask_email_handle(update: Update, context: CallbackContext) -> int:
    logger.info("📨 Получен email от пользователя")
    email = update.message.text.strip()

    if not is_valid_email(email):
        keyboard = [[InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text="Некорректный e-mail. Пожалуйста, введите корректный e-mail:",
            reply_markup=reply_markup
        )
        return ASK_EMAIL

    order_code = context.user_data['order_code']
    order_id = context.user_data['order_id']
    selected_courses = context.user_data.get('selected_courses', [])  # список course_key
    pdb.update_email(order_code, email)
    context.user_data['email'] = email

    email_msg = context.user_data.get('email_msg')
    user_id = update.effective_user.id

    try:
        if email_msg:
            await context.bot.delete_message(chat_id=user_id, message_id=email_msg.message_id)
        await update.message.delete()
    except Exception as e:
        logger.error(f"Ошибка удаления сообщения: {e}")

    # Определяем тип подписки и цену
    is_test_subscription = context.user_data.get('is_test_subscription', False)
    
    if is_test_subscription:
        # Для тестовых подписок
        text_lines = [f"📧 Email: {email}"]
        text_lines.append("🧪 Тестовая подписка на 2 дня")
        total_price = config.courses['course']['test_price']  # 1 рубль
        text_lines.append(f"💰 Сумма: {total_price} руб.")
    else:
        # Для обычных подписок
        text_lines = [config.bot_msg['confirm_purchase_header'].format(email=email)]
        
        # Каждая строка курса
        total_price = 0
        for course_key in selected_courses:
            course = config.courses[course_key]
            line = config.bot_msg['confirm_purchase_course_line'].format(
                name=course['name'] + course['emoji'],
                price=course['price']
            )
            text_lines.append(line)
            total_price += course['price']
        
        # Итог
        text_lines.append(config.bot_msg['confirm_purchase_footer'].format(total=total_price))

    text = "\n".join(text_lines)
    
    # Специальная цена для тестировщиков
    if user_id == 7768888247 or user_id == 5738018066:
        total_price = 2

    # Создаём платёж
    if is_test_subscription:
        payment_url = payment.create_test_payment_robokassa(
            email=email,
            order_code=order_code,
            order_id=order_id,
            user_id=user_id
        )
    else:
        payment_url = payment.create_payment_robokassa(
            price=total_price,
            email=email,
            num_of_chapter=",".join(selected_courses),
            order_code=order_code,
            order_id=order_id,
            user_id=user_id)

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и оплатить", url=payment_url)],
        [InlineKeyboardButton("🚫 Отмена", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    payment_message = await update.message.chat.send_message(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    payment_message_id = payment_message.message_id
    pdb.update_payment_message_id(order_code, payment_message_id)

    context.user_data.clear()
    return ConversationHandler.END


# Отмена
async def cancel_payment_handle(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data.clear()
    keyboard = [
        [InlineKeyboardButton("📲 Главное меню", callback_data='main_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "Покупка отменена. Возвращайтесь позже."
    await send_or_edit_message(update, context, text, reply_markup)
    return ConversationHandler.END


async def buy_multiply_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    not_bought_courses = pdb.get_not_bought_courses(user_id)

    if not not_bought_courses:
        text = "Вы уже приобрели все доступные курсы."
        reply_markup = InlineKeyboardMarkup(my_keyboard.main_menu_button_markup())
    else:
        # Получаем уже выбранные курсы из context.user_data
        selected = context.user_data.get("multi_buy_selected", [])

        keyboard = my_keyboard.ch_choose_button(
            available_courses=not_bought_courses,
            mode='multi_buy',
            selected=selected
        )
        keyboard += my_keyboard.buy_multiply_menu_items_button()
        keyboard.extend(my_keyboard.main_menu_button_markup())
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Выберите курсы, которые хотите купить. Нажмите ещё раз, чтобы снять выбор."

    await send_or_edit_message(update, context, text, reply_markup)


async def toggle_multi_buy_chapter(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data  # Пример: "multi_buy_chapter:default"
    course_key = 'course'  # У нас только один курс

    selected = context.user_data.get("multi_buy_selected", [])

    if course_key in selected:
        selected.remove(course_key)
    else:
        selected.append(course_key)

    context.user_data["multi_buy_selected"] = selected

    not_bought_courses = pdb.get_not_bought_courses(user_id)

    keyboard = my_keyboard.ch_choose_button(
        available_courses=not_bought_courses,
        mode='multi_buy',
        selected=selected
    )
    keyboard += my_keyboard.buy_multiply_menu_items_button()
    keyboard.extend(my_keyboard.main_menu_button_markup())
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "Выберите курсы, которые хотите купить. Нажмите ещё раз, чтобы снять выбор."
    await send_or_edit_message(update, context, text, reply_markup)


async def clear_selected_multi_buy_callback_handle(update: Update, context: CallbackContext) -> None:
    context.user_data.pop("multi_buy_selected", None)
    await buy_multiply_callback_handle(update, context)


async def upd_payment_url_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    order_code = data.split(':')[1]
    order_data = pdb.get_order_by_code(int(order_code))

    # У нас только один курс
    course = config.courses.get('course')
    user_id = order_data['user_id']
    email = order_data['email']
    course_key = 'course'
    order_id = order_data['order_id']

    payment_url = await payment.create_payment(
        price=course['price'],
        user_id=user_id,
        email=email,
        num_of_chapter=course_key,
        order_id=order_id,
        order_code=order_code
    )

    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить и оплатить", url=payment_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = config.bot_msg['confirm_purchase'].format(
        email=email,
        name=course['name'] + course['emoji'],
        num=course_key,
        price=course['price'],
    )
    payment_message = await send_or_edit_message(update, context, text, reply_markup)

    payment_message_id = payment_message.message_id
    pdb.update_payment_message_id(order_code, payment_message_id)


async def handle_join_request(update: Update, context: CallbackContext):
    join_request = update.chat_join_request
    user_id = join_request.from_user.id
    chat_id = update.chat_join_request.chat.id

    logger.info(f"🔄 Получен запрос на вступление от пользователя {user_id} в чат {chat_id}")

    # if user_id == 7768888247:
    #     user_id = 146679674
    # if user_id == 146679674:
    #     await join_request.approve()
    #     return
    channel_data = config.channel_map.get(chat_id)

    logger.info(f"📊 channel_data для {chat_id}: {channel_data}")

    if channel_data:
        name = channel_data.get('name')
        channel_invite_link = channel_data.get('channel_invite_link')
        group_invite_link = channel_data.get('group_invite_link')
    else:
        return

    # У нас только один курс
    course_key = 'course'
    logger.info(f"course_key! = {course_key}")

    # Проверяем активную подписку или ручной доступ
    if pdb.has_manual_access(user_id, course_key) or pdb.has_active_subscription(user_id):
        await join_request.approve()
        keyboard = [
            [InlineKeyboardButton("✅ Перейти в канал", url=channel_invite_link)],
            [InlineKeyboardButton("✅ Вступить в группу", url=group_invite_link)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=config.bot_msg['channel_access_granted'].format(channel_name=name),
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        logger.info(f"✅ Одобрен вход для пользователя {user_id}")
    else:
        await join_request.decline()
        keyboard = [
            [InlineKeyboardButton("✅ Выдать доступ", callback_data=f"grant_access:{user_id}:course")],
            [InlineKeyboardButton("❌ Не выдавать доступ", callback_data=f"deny_access:{user_id}:course")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=config.cfg['ADMIN_CHAT_ID']['MAIN'],
            text=f"❌ Пользователь {user_id} был отклонён при попытке вступить в {name}. Хотите выдать ему доступ?",
            reply_markup=reply_markup,
            message_thread_id=config.cfg['ADMIN_CHAT_ID']['DECLINED_REQUESTS']
        )


async def grant_manual_access_handle(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    _, user_id_str, course_key = query.data.split(":")
    user_id = int(user_id_str)
    admin_id = query.from_user.id
    course = config.courses.get('course')
    name = course['name'] + course['emoji']
    # Добавим доступ в manual_access
    try:
        pdb.grant_manual_access(user_id=user_id, granted_by=admin_id)
        text = (
            f"✅ Доступ пользователю {user_id} к курсу {name} успешно выдан. Теперь ему нужно заново перейти в канал."
        )
        await send_or_edit_message(update, context, text)
    except Exception as e:
        logger.error(f"❌ Ошибка выдачи доступа: {e}")
        text = "❌ Ошибка при попытке выдать доступ."
        await send_or_edit_message(update, context, text)


async def deny_manual_access(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    _, user_id_str, course_key = query.data.split(":")
    text = f"⛔️ Вы отказали в доступе пользователю {user_id_str} к курсу."
    await send_or_edit_message(update, context, text)


async def go_back_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    menu_path = query.data.split(':')[1]
    if menu_path == 'all_courses':
        await all_courses_command(update, context)
    elif menu_path == 'my_courses':
        await my_courses_command(update, context)
    else:
        await buy_courses_command(update, context)


async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message_base = (
        "An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    )

    # Разбиение tb_string на части, если общее сообщение превышает 4096 символов
    max_length = 4096 - len(message_base) - 100  # Вычитаем длину основного сообщения и резервируем место
    parts = [tb_string[i:i + max_length] for i in range(0, len(tb_string), max_length)]

    # Отправляем базовую часть сообщения
    await context.bot.send_message(
        chat_id=config.cfg['ADMIN_CHAT_ID']['MAIN'], text=message_base, parse_mode=ParseMode.HTML,
        message_thread_id=config.cfg['ADMIN_CHAT_ID']['LOGS']
    )

    # Отправляем каждую часть traceback по отдельности
    for part in parts:
        message = f"<pre>{html.escape(part)}</pre>"
        await context.bot.send_message(
            chat_id=config.cfg['ADMIN_CHAT_ID']['MAIN'], text=message, parse_mode=ParseMode.HTML,
            message_thread_id=config.cfg['ADMIN_CHAT_ID']['LOGS']
        )


async def post_init(application: Application) -> None:
    # Подгружаем команды из main_menu
    menu_commands = [
        BotCommand(f"/{key}", value) for key, value in config.bot_btn['main_menu'].items()
    ]

    # Устанавливаем только эти 3 команды
    await application.bot.set_my_commands(menu_commands)


buy_course_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(pay_chapter_callback_handle, pattern="^pay_chapter"),
        CallbackQueryHandler(confirm_multi_buy_handle, pattern="^confirm_buy_multiply$")
    ],
    states={
        AGREE_OFFER: [CallbackQueryHandler(handle_offer_agree, pattern="^agree_offer:")],
        AGREE_PRIVACY: [CallbackQueryHandler(handle_privacy_agree, pattern="^agree_privacy:")],
        AGREE_NEWSLETTER: [
            CallbackQueryHandler(handle_newsletter_agree, pattern="^(agree_newsletter:|disagree_newsletter:)")
        ],
        ASK_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_email_handle)],
    },
    fallbacks=[CallbackQueryHandler(cancel_payment_handle, pattern="^cancel$")],
    allow_reentry=True
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
        .post_init(post_init)
        .build()
    )

    # Запускаем ежедневную синхронизацию job_queue с БД
    schedule_daily_sync(application)

    application.add_handler(CommandHandler('start', register))
    # application.add_handler(CommandHandler('my_courses', my_courses_command))
    # application.add_handler(CommandHandler('all_courses', all_courses_command))
    application.add_handler(CommandHandler('documents', documents_command))
    application.add_handler(CommandHandler('support', support_command))
    application.add_handler(CommandHandler('cancel_sub', cancel_sub_command))
    application.add_handler(CommandHandler('zxc', zxc_command))
    application.add_handler(CommandHandler('sync_jobs', sync_jobs_command))
    application.add_handler(CommandHandler('jobs_list', jobs_list_command))

    application.add_handler(CallbackQueryHandler(start_callback_handle, pattern="^start$"))
    application.add_handler(CallbackQueryHandler(buy_courses_callback_handle, pattern="^buy_courses$"))
    application.add_handler(CallbackQueryHandler(buy_chapter_callback_handle, pattern="^buy_chapter$"))

    # application.add_handler(CallbackQueryHandler(buy_multiply_callback_handle, pattern="^buy_multiply$"))

    # application.add_handler(CallbackQueryHandler(toggle_multi_buy_chapter, pattern="^multi_buy_chapter:"))

    application.add_handler(CallbackQueryHandler(go_back_callback_handle, pattern="^go_back:"))

    # application.add_handler(CallbackQueryHandler(clear_selected_multi_buy_callback_handle,
    #                                              pattern="^clear_buy_multiply$"))

    application.add_handler(CallbackQueryHandler(upd_payment_url_handle, pattern="^upd_payment_url:"))

    application.add_handler(CallbackQueryHandler(main_menu_callback_handle, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(my_courses_callback_handle, pattern="^my_courses$"))
    # application.add_handler(CallbackQueryHandler(all_courses_callback_handle,
    #                                              pattern=r"^(all_courses|go_back_buy_multiply)$"))
    application.add_handler(CallbackQueryHandler(documents_callback_handle, pattern="^documents$"))
    application.add_handler(CallbackQueryHandler(support_callback_handle, pattern="^support$"))

    application.add_handler(CallbackQueryHandler(grant_manual_access_handle, pattern="^grant_access:"))
    application.add_handler(CallbackQueryHandler(deny_manual_access, pattern="^deny_access:"))

    application.add_handler(CallbackQueryHandler(cancel_sub_confirm_callback, pattern="^cancel_sub_confirm$"))
    application.add_handler(CallbackQueryHandler(cancel_sub_final_callback, pattern="^cancel_sub_final$"))
    application.add_handler(CallbackQueryHandler(cancel_sub_keep_callback, pattern="^cancel_sub_keep$"))
    application.add_handler(CallbackQueryHandler(cancel_sub_menu_callback, pattern="^cancel_sub$"))
    application.add_handler(CallbackQueryHandler(test_sub_callback_handle, pattern="^test_sub$"))

    application.add_handler(buy_course_conversation)
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_error_handler(error_handler)

    logger.addHandler(logging.StreamHandler())

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    run()
