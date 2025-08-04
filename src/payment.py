import config
from yookassa import Configuration, Payment
from robokassa.robokassa import HashAlgorithm, Robokassa
from robokassa.robokassa.types import InvoiceType
import logging

# Настройка формата и уровня логгирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
# Создание логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# Получите логгер для модуля 'httpx'
logger_for_httpx = logging.getLogger('httpx')
# Установите уровень логирования на WARNING, чтобы скрыть INFO и DEBUG сообщения
logger_for_httpx.setLevel(logging.WARNING)


robokassa = Robokassa(
    merchant_login=config.config_env['MERCHANT_LOGIN_ROBOKASSA'],
    password1=config.config_env['ROBOKASSA_PASS_1'],
    password2=config.config_env['ROBOKASSA_PASS_2'],
    is_test=False,
    algorithm=HashAlgorithm.sha256,
)

Configuration.account_id = config.config_env['SHOP_ID']
Configuration.secret_key = config.config_env['SECRET_KEY']


async def create_payment(price, user_id, email, num_of_chapter, order_id, order_code):
    formatted_chapter = f'ch_{num_of_chapter}'
    course = config.courses.get(formatted_chapter)
    name = course['name']
    short_name_for_receipt = course['short_name_for_receipt']
    payment = Payment.create({
        "amount": {
            "value": str(price),  # Преобразуем цену в строку, как ожидает API
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": config.other_cfg['links']['main']
        },
        "capture": True,
        "test": True,
        "description": f"Доступ к курсу. Заказ #n{order_code}",
        "metadata": {
            "type": "self",
            "user_id": user_id,
            "chapter": formatted_chapter,
            "order_id": order_id
        },
        "receipt": {
            "customer": {
                "email": email
            },
            "items": [
                {
                    "description": f"{short_name_for_receipt}",
                    "quantity": "1",
                    "amount": {
                        "value": str(price),  # Цена также должна быть строкой
                        "currency": "RUB"
                    },
                    "vat_code": "1"
                },
            ]
        }
    })

    return payment.confirmation.confirmation_url


def create_payment_robokassa(price, email, num_of_chapter, order_code, order_id, user_id):
    chapter_nums = num_of_chapter.split(',')  # Например: ['1', '2']
    formatted_chapters = [f'ch_{num}' for num in chapter_nums]

    items = []

    for num in chapter_nums:
        chapter_key = f'ch_{num}'
        course = config.courses.get(chapter_key)
        if not course:
            continue

        items.append({
            "Name": f"{course['short_name_for_receipt']}",
            "Quantity": 1,
            "Sum": course['price'],
            "PaymentMethod": "full_prepayment",
            "PaymentObject": "service",
            "Tax": "none"
        })

    # Описание для платёжной ссылки (не чек)
    description = f"Доступ к курсу. #n{order_code}"

    receipt = {"items": items}

    response = robokassa.generate_open_payment_link(
        merchant_comments="no comment",
        description=description,
        invoice_type=InvoiceType.ONE_TIME,
        email=email,
        receipt=receipt,
        inv_id=order_code,
        out_sum=price,
        user_id=user_id,
        recurring=True,
        formatted_chapter=",".join(formatted_chapters),
        order_id=order_id
    )
    logger.info(response)
    return response.url


async def create_recurring_payment_robokassa(price, email, num_of_chapter, order_code, order_id, user_id,
                                             previous_inv_id):
    """
    Создает рекуррентный платеж через Robokassa

    Args:
        price: Сумма платежа
        email: Email пользователя
        num_of_chapter: Номера глав (например: "1,2")
        order_code: Новый код заказа
        order_id: Новый ID заказа
        user_id: ID пользователя
        previous_inv_id: ID первого успешного платежа (для рекуррентных списаний)
    """
    chapter_nums = num_of_chapter.split(',')  # Например: ['1', '2']
    formatted_chapters = [f'ch_{num}' for num in chapter_nums]

    items = []

    for num in chapter_nums:
        chapter_key = f'ch_{num}'
        course = config.courses.get(chapter_key)
        if not course:
            continue

        items.append({
            "Name": f"{course['short_name_for_receipt']}",
            "Quantity": 1,
            "Sum": course['price'],
            "PaymentMethod": "full_prepayment",
            "PaymentObject": "service",
            "Tax": "none"
        })

    # Описание для платёжной ссылки (не чек)
    description = f"Рекуррентный платеж за доступ к курсу. #n{order_code}"

    receipt = {"items": items}

    try:
        result = await robokassa.execute_recurring_payment(
            previous_inv_id=previous_inv_id,  # ID первого успешного платежа
            out_sum=price,
            inv_id=order_code,
            description=description,
            email=email,
            receipt=receipt,
            user_ip=None,  # Если у вас есть функция получения IP
            shp_user_id=user_id,
            shp_formatted_chapter=",".join(formatted_chapters),
            shp_order_id=order_id
        )

        logger.info(f"Recurring payment executed: {result}")
        return result

    except Exception as e:
        logger.error(f"Failed to execute recurring payment: {e}")
        raise e


# Пример использования:
async def charge_monthly_subscription():
    """
    Пример функции для ежемесячного списания подписки
    """
    try:
        # Получаем данные подписки из БД
        first_payment_inv_id = 27167
        user_email = 'ya.matveev116@ya.ru'
        subscription_price = 15

        # Выполняем рекуррентный платеж
        result = await create_recurring_payment_robokassa(
            price=subscription_price,
            email=user_email,
            num_of_chapter='8',
            order_code=34534535,
            order_id=9899,
            user_id=146679674,
            previous_inv_id=first_payment_inv_id  # ← ID первого платежа
        )

        return result

    except Exception as e:
        logger.error(f"Monthly subscription charge failed for user: {e}")
        # Здесь можно добавить логику уведомления пользователя об ошибке
        raise e
