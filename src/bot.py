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
import other_func
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


async def send_or_edit_message(update: Update, context: CallbackContext, text: str,
                               reply_markup: InlineKeyboardMarkup = None, new_message=False):
    if new_message:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    if update.callback_query:
        if update.callback_query.message.text:
            await update.callback_query.edit_message_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        else:
            await update.callback_query.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    else:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )


async def register(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or ""
    last_name = update.effective_user.last_name or ""
    username = update.effective_chat.username or ""

    # Добавление пользователя в БД
    if not await user_exists_pdb(user_id):
        pdb.add_user(user_id, username, first_name, last_name)

    keyboard = [[InlineKeyboardButton(config.bot_btn['buy_courses'], callback_data='pay_chapter:course')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=user_id,
        text=f"{config.bot_msg['hello'].format(first_name=first_name)}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END


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
    text = config.bot_msg['sub']['cancel']
    keyboard = [
        [InlineKeyboardButton(config.bot_btn['sub']['cancel'], callback_data="cancel_sub_confirm")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await send_or_edit_message(update, context, text, reply_markup)


async def zxc_command(update: Update, context: CallbackContext) -> None:
    await payment.charge_monthly_subscription()


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
    text = config.bot_msg['sub']['canceled']
    await send_or_edit_message(update, context, text)


async def cancel_sub_keep_callback(update: Update, context: CallbackContext) -> None:
    text = config.bot_msg['sub']['cancel_keep']
    await send_or_edit_message(update, context, text)


async def main_menu_callback_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        text="📲 Главное меню",
        reply_markup=my_keyboard.main_menu_items_button_markup(),
        parse_mode=ParseMode.HTML
    )


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

    course_key = query.data.split(':')[1]
    try:
        menu_path = query.data.split(':')[2]
    except Exception:
        menu_path = 'default'

    course = config.courses.get(course_key)

    if not course:
        await query.edit_message_text("Курс не найден.")
        return

    text = config.bot_msg['buy_chapter_info'].format(
        name=course['name'] + course['emoji'],
        description=course['description'],
        price=course['price']
    )

    keyboard = []

    if pdb.has_paid_course(user_id, course_key) or pdb.has_manual_access(user_id, course_key):
        keyboard.append([
            InlineKeyboardButton(config.bot_btn['go_to_channel'], url=course['channel_invite_link'])
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(config.bot_btn['go_to_pay'], callback_data=f'pay_chapter:{course_key}')
        ])

    keyboard.append([
        InlineKeyboardButton(config.bot_btn['go_back'], callback_data=f'go_back:{menu_path}')
    ])

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
    user_id = query.from_user.id

    course_key = query.data.split(':')[1]
    course = config.courses.get(course_key)

    if not course:
        await query.edit_message_text("Курс не найден.")
        return ConversationHandler.END

    order_code = other_func.generate_order_number()
    order_id = pdb.create_order(user_id=user_id, course_chapter=course_key, order_code=order_code)
    context.user_data['selected_course'] = course
    context.user_data['course_key'] = course_key
    context.user_data['order_id'] = order_id

    context.user_data['is_in_conversation'] = True

    keyboard = [
        [InlineKeyboardButton("✅ Принимаю", callback_data=f"agree_offer:{order_code}")],
        [InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="📄 Я ознакомился и принимаю условия Публичной оферты.\n\n"
             f'<a href="{config.other_cfg["links"]["offer"]}">Открыть оферту</a>',
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    # return AGREE_OFFER
    return await start_payment_handle(update, context, [course_key])


async def confirm_multi_buy_handle(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    await query.answer()

    selected_courses = context.user_data.get("multi_buy_selected", [])
    user_id = query.from_user.id

    if not selected_courses:
        await query.edit_message_text("❗️Вы не выбрали ни одного курса.")
        return ConversationHandler.END

    context.user_data['is_in_conversation'] = True
    context.user_data['multi_buy_selected'] = selected_courses

    # Переход в общий обработчик запуска оплаты
    return await start_payment_handle(update, context, selected_courses)


async def start_payment_handle(update: Update, context: CallbackContext, selected_courses: list) -> int:
    query = update.callback_query
    user_id = query.from_user.id

    # Теперь у нас только один курс, берем первый из списка
    course_key = selected_courses[0] if selected_courses else 'course'
    order_code = other_func.generate_order_number()
    order_id = pdb.create_order(user_id=user_id, course_chapter=course_key, order_code=order_code)

    context.user_data['selected_courses'] = selected_courses
    context.user_data['order_id'] = order_id
    context.user_data['order_code'] = order_code

    keyboard = [
        [InlineKeyboardButton("✅ Принимаю", callback_data=f"agree_offer:{order_code}")],
        [InlineKeyboardButton("🚫 Отмена", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="📄 Я ознакомился и принимаю условия Публичной оферты.\n\n"
             f'<a href="{config.other_cfg["links"]["offer"]}">Открыть оферту</a>',
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
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

    await query.edit_message_text(
        text='🔐 Я даю согласие на обработку моих персональных данных.\n\n'
             f'<a href="{config.other_cfg["links"]["privacy"]}">Политика обработки данных</a>',
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
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

    await query.edit_message_text(
        text="📬 Я даю согласие на получение рекламной и информационной рассылки.\n\n"
             f'<a href="{config.other_cfg["links"]["consent"]}">Документ о рассылке</a>',
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
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
    email_msg = await query.edit_message_text(text="📧 Введите ваш e-mail для отправки чека:",
                                              reply_markup=reply_markup)
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

    text_lines = [config.bot_msg['confirm_purchase_header'].format(email=email)]
    # Заголовок

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
    if user_id == 146679674:
        total_price = 15
    # Создаём платёж
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
    if user_id == 146679674:
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
    await query.edit_message_text(text="Покупка отменена. Возвращайтесь позже.",
                                  reply_markup=reply_markup)
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

    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def toggle_multi_buy_chapter(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data  # Пример: "multi_buy_chapter:course"
    course_key = data.split(":")[1]

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

    await query.edit_message_text(
        text="Выберите курсы, которые хотите купить. Нажмите ещё раз, чтобы снять выбор.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )


async def clear_selected_multi_buy_callback_handle(update: Update, context: CallbackContext) -> None:
    context.user_data.pop("multi_buy_selected", None)
    await buy_multiply_callback_handle(update, context)


async def upd_payment_url_handle(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    order_code = data.split(':')[1]
    order_data = pdb.get_order_by_code(int(order_code))

    course = config.courses.get(order_data['course_chapter'])
    user_id = order_data['user_id']
    email = order_data['email']
    course_key = order_data['course_chapter']
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
    payment_message = await query.edit_message_text(
        text=config.bot_msg['confirm_purchase'].format(
            email=email,
            name=course['name'] + course['emoji'],
            num=course_key,
            price=course['price'],
        ),
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

    payment_message_id = payment_message.message_id
    pdb.update_payment_message_id(order_code, payment_message_id)


async def handle_join_request(update: Update, context: CallbackContext):
    join_request = update.chat_join_request
    user_id = join_request.from_user.id
    chat_id = update.chat_join_request.chat.id
    if user_id == 146679674:
        await join_request.approve()
        return
    channel_data = config.channel_map.get(chat_id)

    if channel_data:
        name = channel_data.get('name')
        channel_invite_link = channel_data.get('channel_invite_link')
    else:
        return

    course_key = config.channel_id_to_key.get(chat_id)
    logger.info(f"course_key! = {course_key}")

    if pdb.has_manual_access(user_id, course_key) or pdb.has_paid_course(user_id, course_key):
        await join_request.approve()
        keyboard = [
            [InlineKeyboardButton("✅ Перейти в канал", url=channel_invite_link)],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=user_id,
            text=f"Для перехода в канал ({name}) нажмите на кнопку ниже",
            reply_markup=reply_markup
        )
        logger.info(f"✅ Одобрен вход для {allowed_users[user_id]} ({user_id})")
    else:
        await join_request.decline()
        keyboard = [
            [InlineKeyboardButton("✅ Выдать доступ", callback_data=f"grant_access:{user_id}:{course_key}")],
            [InlineKeyboardButton("❌ Не выдавать доступ", callback_data=f"deny_access:{user_id}:{course_key}")]
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
    course = config.courses.get(course_key)
    name = course['name'] + course['emoji']
    # Добавим доступ в manual_access
    try:
        pdb.grant_manual_access(user_id=user_id, course_chapter=course_key, granted_by=admin_id)
        await query.edit_message_text(
            f"✅ Доступ пользователю {user_id} к курсу {name} успешно выдан. Теперь ему нужно заново перейти в канал.")
    except Exception as e:
        logger.error(f"❌ Ошибка выдачи доступа: {e}")
        await query.edit_message_text("❌ Ошибка при попытке выдать доступ.")


async def deny_manual_access(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    _, user_id_str, course_key = query.data.split(":")
    await query.edit_message_text(f"⛔️ Вы отказали в доступе пользователю {user_id_str} к курсу {course_key}.")


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
        CallbackQueryHandler(pay_chapter_callback_handle, pattern="^pay_chapter:"),
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

    application.add_handler(CommandHandler('start', register))
    # application.add_handler(CommandHandler('my_courses', my_courses_command))
    # application.add_handler(CommandHandler('all_courses', all_courses_command))
    application.add_handler(CommandHandler('documents', documents_command))
    application.add_handler(CommandHandler('support', support_command))
    application.add_handler(CommandHandler('cancel_sub', cancel_sub_command))
    application.add_handler(CommandHandler('zxc', zxc_command))

    application.add_handler(CallbackQueryHandler(buy_courses_callback_handle, pattern="^buy_courses$"))
    application.add_handler(CallbackQueryHandler(buy_chapter_callback_handle, pattern="^buy_chapter:"))

    application.add_handler(CallbackQueryHandler(buy_multiply_callback_handle, pattern="^buy_multiply$"))

    application.add_handler(CallbackQueryHandler(toggle_multi_buy_chapter, pattern="^multi_buy_chapter:"))

    application.add_handler(CallbackQueryHandler(go_back_callback_handle, pattern="^go_back:"))

    application.add_handler(CallbackQueryHandler(clear_selected_multi_buy_callback_handle,
                                                 pattern="^clear_buy_multiply$"))

    application.add_handler(CallbackQueryHandler(upd_payment_url_handle, pattern="^upd_payment_url:"))

    application.add_handler(CallbackQueryHandler(main_menu_callback_handle, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(my_courses_callback_handle, pattern="^my_courses$"))
    application.add_handler(CallbackQueryHandler(all_courses_callback_handle,
                                                 pattern=r"^(all_courses|go_back_buy_multiply)$"))
    application.add_handler(CallbackQueryHandler(documents_callback_handle, pattern="^documents$"))
    application.add_handler(CallbackQueryHandler(support_callback_handle, pattern="^support$"))

    application.add_handler(CallbackQueryHandler(grant_manual_access_handle, pattern="^grant_access:"))
    application.add_handler(CallbackQueryHandler(deny_manual_access, pattern="^deny_access:"))

    application.add_handler(CallbackQueryHandler(cancel_sub_confirm_callback, pattern="^cancel_sub_confirm$"))
    application.add_handler(CallbackQueryHandler(cancel_sub_final_callback, pattern="^cancel_sub_final$"))
    application.add_handler(CallbackQueryHandler(cancel_sub_keep_callback, pattern="^cancel_sub_keep$"))

    application.add_handler(buy_course_conversation)
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_error_handler(error_handler)

    logger.addHandler(logging.StreamHandler())

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    run()
