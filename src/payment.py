import config
from yookassa import Configuration, Payment

Configuration.account_id = config.config_env['SHOP_ID']
Configuration.secret_key = config.config_env['SECRET_KEY']


async def create_payment(price, user_id, num_of_chapter):
    course = config.courses.get(f'ch_{num_of_chapter}')
    name = course['name']
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
        "description": f"Доступ к разделу курса {name}",
        "metadata": {
            "type": "self",
            "user_id": user_id,
            "chapter": course,
        },
        "receipt": {
            "customer": {
                "email": "ya.matveev116@ya.ru"
            },
            "items": [
                {
                    "description": f"Доступ к разделу курса {name}",
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
