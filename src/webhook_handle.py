from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import config
import payment
import telegram_https
from fastapi import Request
from setup import pdb, moscow_tz
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешает все источники
    allow_credentials=True,
    allow_methods=["*"],  # Разрешает все методы
    allow_headers=["*"],  # Разрешает все заголовки
)


@app.post("/webhook/yookassa/")
async def yookassa_webhook(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    payment_object = data.get('object', {})
    payment_id = payment_object.get('id')

    # Проверяем, был ли платеж уже обработан
    if pdb.payment_exists(payment_id):
        logger.info(f"Payment {payment_id} already processed. Skipping.")
        return {"status": "ok"}

    amount = float(payment_object.get('amount', {}).get('value'))
    income_amount = float(
        payment_object.get('income_amount', {}).get('value', 0.0))  # Обработка, если income_amount отсутствует
    payment_method_type = payment_object.get('payment_method', {}).get('type', 'test')

    user_id = int(payment_object.get('metadata', {}).get('user_id'))
    chapter = payment_object.get('metadata', {}).get('chapter', '')
    order_id = int(payment_object.get('metadata', {}).get('order_id', ''))
    course = config.courses.get(chapter)

    channel_invite_url = course['channel_invite_link']
    channel_name = course['name']

    pdb.add_payment(external_payment_id=payment_id, amount=amount, income_amount=income_amount,
                          payment_method_type=payment_method_type, order_id=order_id)

    keyboard = [
        [InlineKeyboardButton("Вступить в канал ✅", url=channel_invite_url)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await telegram_https.send_message(
        user_id=user_id,
        text=f"Для вступления в канал <b>({channel_name}</b> нажмите на кнопку ниже",
        reply_markup=reply_markup
    )
    return {"status": "ok"}


@app.post("/webhook/robokassa/")
async def robokassa_webhook(request: Request, background_tasks: BackgroundTasks):
    logger.info(request)

    form = await request.form()
    logger.info(f"FORMMMM = {form})
    # data = await request.json()
    # payment_object = data.get('object', {})
    # payment_id = payment_object.get('id')
    #
    # # Проверяем, был ли платеж уже обработан
    # if pdb.payment_exists(payment_id):
    #     logger.info(f"Payment {payment_id} already processed. Skipping.")
    #     return {"status": "ok"}
    #
    # amount = float(payment_object.get('amount', {}).get('value'))
    # income_amount = float(
    #     payment_object.get('income_amount', {}).get('value', 0.0))  # Обработка, если income_amount отсутствует
    # payment_method_type = payment_object.get('payment_method', {}).get('type', 'test')
    #
    # user_id = int(payment_object.get('metadata', {}).get('user_id'))
    # chapter = payment_object.get('metadata', {}).get('chapter', '')
    # order_id = int(payment_object.get('metadata', {}).get('order_id', ''))
    # course = config.courses.get(chapter)
    #
    # channel_invite_url = course['channel_invite_link']
    # channel_name = course['name']
    #
    # pdb.add_payment(external_payment_id=payment_id, amount=amount, income_amount=income_amount,
    #                       payment_method_type=payment_method_type, order_id=order_id)
    #
    # keyboard = [
    #     [InlineKeyboardButton("Вступить в канал ✅", url=channel_invite_url)],
    # ]
    # reply_markup = InlineKeyboardMarkup(keyboard)
    #
    # await telegram_https.send_message(
    #     user_id=user_id,
    #     text=f"Для вступления в канал <b>({channel_name}</b> нажмите на кнопку ниже",
    #     reply_markup=reply_markup
    # )
    return {"status": "ok"}
