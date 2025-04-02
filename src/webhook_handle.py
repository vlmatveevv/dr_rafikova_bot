from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import config
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
    user_id = int(payment_object.get('metadata', {}).get('user_id'))
    chapter = payment_object.get('metadata', {}).get('chapter', '')
    course = config.courses.get(chapter)

    channel_invite_url = course['channel_invite_link']

    keyboard = [
        [InlineKeyboardButton("Вступить в канал ✅", url=channel_invite_url)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await telegram_https.send_message(
        user_id=user_id,
        text=channel_invite_url,
        reply_markup=reply_markup
    )
    return {"status": "ok"}
