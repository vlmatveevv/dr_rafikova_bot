import aiohttp
import config
import logging

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def send_message(user_id: int, text, reply_markup=None, message_thread_id=None, reply_to_message_id=None,
                       disable_web_page_preview=True):
    # Проверяем, соответствует ли событие успешной оплате
    async with aiohttp.ClientSession() as session:
        # Здесь необходимо указать ваш токен и chat_id
        url = f"https://api.telegram.org/bot{config.cfg['TELEGRAM_TOKEN']}/sendMessage"
        payload = {
            'chat_id': user_id,  # Укажите chat_id группы
            'text': text,
            'parse_mode': 'HTML',
            'disable_web_page_preview': disable_web_page_preview,
        }

        # Если передан message_thread_id, добавляем его в payload
        if message_thread_id is not None:
            payload['message_thread_id'] = message_thread_id

        # Если передан reply_to_message_id, добавляем его в payload для ответа на сообщение
        if reply_to_message_id is not None:
            payload['reply_to_message_id'] = reply_to_message_id

        # Преобразуем InlineKeyboardMarkup в JSON
        if reply_markup is not None:
            payload['reply_markup'] = reply_markup.to_dict()  # Преобразуем в формат JSON для отправки

        async with session.post(url, json=payload) as response:
            response_data = await response.json()
            if response.status == 200:
                logger.info("Message sent to Telegram successfully")
            else:
                logger.error(f"Failed to send message to Telegram: {response_data}")


async def send_location(user_id: int, latitude: float, longitude: float):
    # Проверяем, соответствует ли событие успешной оплате
    async with aiohttp.ClientSession() as session:
        # Здесь необходимо указать ваш токен и chat_id
        url = f"https://api.telegram.org/bot{config.cfg['TELEGRAM_TOKEN']}/sendLocation"
        payload = {
            'chat_id': user_id,  # Укажите chat_id группы
            'latitude': latitude,
            'longitude': longitude,
        }

        async with session.post(url, json=payload) as response:
            response_data = await response.json()
            if response.status == 200:
                logger.info("Message sent to Telegram successfully")
            else:
                logger.error(f"Failed to send message to Telegram: {response_data}")


async def send_photo(user_id: int, photo, reply_markup=None, message_thread_id=None, reply_to_message_id=None,
                     disable_web_page_preview=True):
    # Проверяем, соответствует ли событие успешной оплате
    async with aiohttp.ClientSession() as session:
        # Здесь необходимо указать ваш токен и chat_id
        url = f"https://api.telegram.org/bot{config.cfg['TELEGRAM_TOKEN']}/sendPhoto"
        payload = {
            'chat_id': user_id,  # Укажите chat_id группы
            'photo': text,
            'disable_web_page_preview': disable_web_page_preview,
        }

        # Если передан message_thread_id, добавляем его в payload
        if message_thread_id is not None:
            payload['message_thread_id'] = message_thread_id

        # Если передан reply_to_message_id, добавляем его в payload для ответа на сообщение
        if reply_to_message_id is not None:
            payload['reply_to_message_id'] = reply_to_message_id

        # Преобразуем InlineKeyboardMarkup в JSON
        if reply_markup is not None:
            payload['reply_markup'] = reply_markup.to_dict()  # Преобразуем в формат JSON для отправки

        async with session.post(url, json=payload) as response:
            response_data = await response.json()
            if response.status == 200:
                logger.info("Message sent to Telegram successfully")
            else:
                logger.error(f"Failed to send message to Telegram: {response_data}")


async def edit_reply_markup(chat_id: int, message_id: int, reply_markup: dict):
    """
    Изменяет reply_markup для сообщения в Telegram.

    :param chat_id: ID чата.
    :param message_id: ID сообщения, для которого нужно изменить клавиатуру.
    :param reply_markup: Словарь с текстом кнопок и их callback_data.
    """
    async with aiohttp.ClientSession() as session:
        # Формируем URL для запроса
        url = f"https://api.telegram.org/bot{config.cfg['TELEGRAM_TOKEN']}/editMessageReplyMarkup"

        # Преобразуем reply_markup в формат JSON для Telegram API
        inline_keyboard = [
            [{"text": text, "callback_data": callback_data}]
            for text, callback_data in reply_markup.items()
        ]
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reply_markup': {"inline_keyboard": inline_keyboard}
        }

        async with session.post(url, json=payload) as response:
            response_data = await response.json()
            if response.status == 200 and response_data.get("ok"):
                logger.info("Reply markup updated successfully")
            else:
                logger.error(f"Failed to update reply markup: {response_data}")


async def delete_message(chat_id: int, message_id: int):
    """
    Удаляет сообщение в Telegram.

    :param chat_id: ID чата (или пользователя), откуда нужно удалить сообщение.
    :param message_id: ID сообщения, которое нужно удалить.
    """
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{config.cfg['TELEGRAM_TOKEN']}/deleteMessage"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id
        }

        async with session.post(url, json=payload) as response:
            response_data = await response.json()
            if response.status == 200 and response_data.get("ok"):
                logger.info(f"✅ Сообщение {message_id} успешно удалено у {chat_id}")
            else:
                logger.error(f"❌ Ошибка при удалении сообщения {message_id} у {chat_id}: {response_data}")


async def create_invite_link(chat_id: int, name: str = None, expire_date: int = None, member_limit: int = 1, creates_join_request: bool = False):
    """
    Создаёт персональную ссылку на приглашение в канал/группу.

    :param chat_id: ID канала или группы (с `@` или числовой).
    :param name: Название ссылки (необязательно).
    :param expire_date: UNIX timestamp — время, когда ссылка истекает.
    :param member_limit: Максимум пользователей по ссылке (по умолчанию 1).
    :param creates_join_request: Требуется ли одобрение (по умолчанию False).
    :return: Словарь с результатом или None при ошибке.
    """
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{config.cfg['TELEGRAM_TOKEN']}/createChatInviteLink"
        payload = {
            'chat_id': chat_id,
            'member_limit': member_limit,
            'creates_join_request': creates_join_request
        }

        if name:
            payload['name'] = name
        if expire_date:
            payload['expire_date'] = expire_date

        async with session.post(url, json=payload) as response:
            response_data = await response.json()
            if response.status == 200 and response_data.get("ok"):
                invite_link = response_data['result']['invite_link']
                logger.info(f"🔗 Ссылка создана: {invite_link}")
                return response_data['result']
            else:
                logger.error(f"❌ Ошибка при создании ссылки: {response_data}")
                return None