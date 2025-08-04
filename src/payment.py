import config
from yookassa import Configuration, Payment
from robokassa.robokassa import HashAlgorithm, Robokassa
from robokassa.robokassa.types import InvoiceType

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


# def create_payment_robokassa(price, email, num_of_chapter, order_code, order_id, user_id):
#     formatted_chapter = f'ch_{num_of_chapter}'
#     course = config.courses.get(formatted_chapter)
#     name = course['name']
#     description = f"Доступ к разделу курса {name}. Заказ #n{order_code}"
#
#     receipt = {
#         "items": [
#             {
#                 "Name": description,
#                 "Quantity": 1,
#                 "Sum": price,
#                 "PaymentMethod": "full_prepayment",
#                 "PaymentObject": "service",
#                 "Tax": "none"
#             }
#         ]
#
#     }
#     response = robokassa.generate_open_payment_link(
#         merchant_comments="no comment",
#         description=description,
#         invoice_type=InvoiceType.ONE_TIME,
#         email=email,
#         receipt=receipt,
#         inv_id=order_code,
#         out_sum=price,
#         user_id=user_id,  # 👈 кастомное поле
#         formatted_chapter=formatted_chapter,  # 👈 ещё одно кастомное поле
#         order_id=order_id  # 👈 и ещё
#     )
#
#     return response.url  # ✅ ВАЖНО: возвращаем строку, а не объект

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

    return response.url
