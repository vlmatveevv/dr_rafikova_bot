from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
import logging
import config
from other_func import escape_user_data
import telegram_https
from fastapi import Request
from setup import pdb, moscow_tz
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from jinja2 import Template

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
    group_invite_url = course.get('group_invite_link')
    channel_name = course['name']

    pdb.add_payment(external_payment_id=payment_id, amount=amount, income_amount=income_amount,
                    payment_method_type=payment_method_type, order_id=order_id)

    keyboard = [
        [InlineKeyboardButton("Вступить в канал ✅", url=channel_invite_url)],
        [InlineKeyboardButton("Вступить в группу ✅", url=group_invite_url)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await telegram_https.send_message(
        user_id=user_id,
        text=f"Для вступления в канал <b>({channel_name}</b> нажмите на кнопку ниже",
        reply_markup=reply_markup
    )
    return {"status": "ok"}


@app.post("/webhook/robokassa/", response_class=PlainTextResponse)
async def robokassa_webhook(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    data = dict(form)
    logger.info(f"📥 Robokassa webhook data: {data}")

    try:
        inv_id = int(data.get("InvId"))  # Это order_code
        out_sum = float(data.get("OutSum", 0))
        payment_method_type = data.get("PaymentMethod", "unknown")
        fee = float(data.get("Fee", 0.0))
        income_amount = out_sum - fee

        user_id = int(data.get("shp_user_id"))
        order_id = int(data.get("shp_order_id"))
        formatted_chapter = data.get("shp_formatted_chapter")
        
        # Определяем тип подписки на основе суммы платежа и параметров webhook
        subscription_type_param = data.get("shp_subscription_type", "regular")
        
        # Дополнительная проверка: если сумма 1 рубль, то это точно тестовая подписка
        if out_sum == 1.0:
            subscription_type_param = "test"
            logger.info(f"🔍 Определена тестовая подписка по сумме платежа: {out_sum} рубль")
        elif out_sum == 990.0:
            subscription_type_param = "regular"
            logger.info(f"🔍 Определена обычная подписка по сумме платежа: {out_sum} рублей")
        else:
            logger.info(f"🔍 Сумма платежа: {out_sum} рублей, тип подписки из параметров: {subscription_type_param}")

        # Проверка: уже обработан?
        if pdb.payment_exists_by_order_code(inv_id):
            logger.info(f"🔁 Платёж по order_code={inv_id} уже обработан. Пропускаем.")
            return "OK"

        # Удаляем сообщение об оплате (если было)
        try:
            payment_message_id = pdb.get_payment_message_id(order_id)
            background_tasks.add_task(
                telegram_https.delete_message,
                chat_id=user_id,
                message_id=payment_message_id
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось удалить сообщение об оплате: {e}")

        # Сохраняем платёж
        pdb.add_payment(
            amount=out_sum,
            income_amount=income_amount,
            payment_method_type=payment_method_type,
            order_id=order_id
        )

        # Проверяем, есть ли уже подписка для этого заказа
        existing_subscription = pdb.get_active_subscription(user_id)

        if existing_subscription:
            # Это повторный платеж - продлеваем подписку
            subscription_type = "renewal"
            try:
                pdb.extend_subscription(existing_subscription['subscription_id'])
                logger.info(f"✅ Подписка {existing_subscription['subscription_id']} продлена")
                logger.info(f"✅ Задача на повторное списание будет добавлена при следующей синхронизации")

                # Отменяем kick задачи для этой подписки
                # К сожалению, у нас нет доступа к context в webhook
                # Kick задачи будут отменены при проверке в kick_subscription_job
                logger.info(f"✅ Kick задачи будут отменены при следующей проверке")

            except Exception as e:
                logger.error(f"❌ Ошибка при продлении подписки: {e}")
                return "OK"
        else:
            # Это первый платеж - создаем подписку
            subscription_type = "new_sub"
            try:
                if subscription_type_param == "test":
                    # Дополнительная проверка суммы для тестовой подписки
                    if out_sum != 1.0:
                        logger.error(f"❌ Несоответствие: тестовая подписка, но сумма {out_sum} рублей (должна быть 1 рубль)")
                        return "OK"
                    
                    # Проверяем, может ли пользователь создать тестовую подписку
                    if not pdb.can_create_test_subscription(user_id):
                        logger.error(f"❌ Пользователь {user_id} не может создать тестовую подписку (уже были подписки)")
                        return "OK"
                    
                    subscription_id = pdb.create_test_subscription(user_id, order_id)
                    logger.info(f"✅ Создана тестовая подписка {subscription_id} для пользователя {user_id}")
                else:
                    # Дополнительная проверка суммы для обычной подписки
                    if out_sum != 990.0:
                        logger.warning(f"⚠️ Необычная сумма для обычной подписки: {out_sum} рублей (ожидалось 990 рублей)")
                    
                    subscription_id = pdb.create_subscription(user_id, order_id)
                    logger.info(f"✅ Создана обычная подписка {subscription_id} для пользователя {user_id}")
                
                logger.info(f"✅ Задача на повторное списание будет добавлена при следующей синхронизации")

            except Exception as e:
                logger.error(f"❌ Ошибка при создании подписки: {e}")
                return "OK"

        # У нас только один курс
        course = config.courses.get('course')
        if not course:
            logger.warning(f"❌ Курс не найден.")
            return "OK"

        course_names = [course["name"]]
        channel_name = course["name"]
        channel_invite_url = course["channel_invite_link"]
        group_invite_url = course.get("group_invite_link")

        keyboard = [
            [InlineKeyboardButton("Вступить в канал ✅", url=channel_invite_url)],
            [InlineKeyboardButton("Вступить в группу ✅", url=group_invite_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Выбираем сообщение в зависимости от типа подписки
        if subscription_type_param == "test":
            message_text = config.bot_msg['test_sub']['activated'].format(channel_name=channel_name)
        else:
            message_text = config.bot_msg['payment_success'].format(channel_name=channel_name)

        background_tasks.add_task(
            telegram_https.send_message,
            user_id=user_id,
            text=message_text,
            reply_markup=reply_markup
        )

        # Подготовка данных о пользователе
        user_info = pdb.get_user_by_user_id(user_id)
        first_name = escape_user_data(user_info.get('first_name', ''))
        last_name = escape_user_data(user_info.get('last_name', ''))
        username = escape_user_data(user_info.get('username', ''))

        user_data = {
            "user_id": user_id,
            "full_name": f"{first_name} {last_name}".strip(),
            "username": username
        }

        # Рендерим блок про пользователя
        user_template_str = config.admin_msg['user_info_block']
        user_info_block = Template(user_template_str).render(**user_data)

        # Определяем тип подписки для админского уведомления
        if subscription_type_param == "test":
            admin_subscription_type = "test_sub"
            logger.info(f"📊 Админское уведомление: тестовая подписка за {out_sum} рубль")
        else:
            admin_subscription_type = subscription_type
            logger.info(f"📊 Админское уведомление: {subscription_type} подписка за {out_sum} рублей")

        # Рендерим общее сообщение админу
        admin_template_str = config.admin_msg['admin_payment_notification']
        admin_payment_notification_text = Template(admin_template_str).render(
            user_info_block=user_info_block,
            channel_names=course_names,
            out_sum=out_sum,
            payment_method_type=payment_method_type,
            income_amount=income_amount,
            user_id=user_id,
            order_code=inv_id,
            formatted_chapters=['course'],
            subscription_type=admin_subscription_type
        )

        # Уведомление администратору
        background_tasks.add_task(
            telegram_https.send_message,
            user_id=config.cfg['ADMIN_CHAT_ID']['MAIN'],
            text=admin_payment_notification_text,
            message_thread_id=config.cfg['ADMIN_CHAT_ID']['PAYMENTS']
        )

        logger.info(f"✅ Платёж InvId={inv_id} от user_id={user_id} успешно обработан.")
        return "OK"

    except Exception as e:
        logger.error(f"❗ Ошибка обработки Robokassa webhook: {e}")
        return "OK"
