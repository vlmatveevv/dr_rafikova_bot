import config
from yookassa import Configuration, Payment
from robokassa import HashAlgorithm, Robokassa
from robokassa.types import InvoiceType

robokassa = Robokassa(
    merchant_login=config.config_env['MERCHANT_LOGIN_ROBOKASSA'],
    password1=config.config_env['ROBOKASSA_PASS_1'],
    password2=config.config_env['ROBOKASSA_PASS_2'],
    is_test=False,
    algorithm=HashAlgorithm.md5,
)

Configuration.account_id = config.config_env['SHOP_ID']
Configuration.secret_key = config.config_env['SECRET_KEY']


async def create_payment(price, user_id, email, num_of_chapter, order_id, order_code):
    formatted_chapter = f'ch_{num_of_chapter}'
    course = config.courses.get(formatted_chapter)
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
        "description": f"Доступ к разделу курса {name}. Заказ #n{order_code}",
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
                    "description": f"Доступ к разделу курса {name}. Заказ #n{order_code}",
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
    formatted_chapter = f'ch_{num_of_chapter}'
    course = config.courses.get(formatted_chapter)
    name = course['name']
    description = f"Доступ к разделу курса {name}. Заказ #n{order_code}"

    response = robokassa.generate_open_payment_link(
        merchant_comments="no comment",
        description=description,
        invoice_type=InvoiceType.ONE_TIME,
        email=email,
        inv_id=order_code,
        out_sum=price,
        user_id=user_id,  # 👈 кастомное поле
        formatted_chapter=formatted_chapter,  # 👈 ещё одно кастомное поле
        order_id=order_id  # 👈 и ещё
    )

    return response.url  # ✅ ВАЖНО: возвращаем строку, а не объект

# async def create_payment_robokassa(price, email, num_of_chapter, order_code, order_id, user_id):
#     formatted_chapter = f'ch_{num_of_chapter}'
#     course = config.courses.get(formatted_chapter)
#     name = course['name']
#     description = f"Доступ к разделу курса {name}. Заказ #n{order_code}"
#
#     receipt = {
#         "sno": "usn_income",
#         "items": [
#             {
#                 "name": f"Доступ к разделу курса {name}",
#                 "quantity": 1,
#                 "sum": price,
#                 "payment_method": "full_prepayment",
#                 "payment_object": "service",
#                 "tax": "none"
#             }
#         ],
#         "email": email
#     }
#
#     response = await robokassa.generate_protected_payment_link(
#         merchant_comments="no comment",
#         description=description,
#         invoice_type=InvoiceType.ONE_TIME,
#         email=email,
#         inv_id=order_code,
#         out_sum=price,
#         receipt=receipt,
#         user_id=user_id,
#         formatted_chapter=formatted_chapter,
#         order_id=order_id
#     )
#
#     return response.url
