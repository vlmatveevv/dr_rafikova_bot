import asyncio

from robokassa import HashAlgorithm, Robokassa
from robokassa.types import InvoiceType


# --- Конфиг ---
MERCHANT_LOGIN = "5389936619"
ALGORITHM = "SHA256"  # можно изменить на SHA256 и т.п.
# Инициализируем robokassa клиент
ROBOKASSA_PASS_1 = "psYjspg6ap45c0NAI9zZ"
ROBOKASSA_PASS_2 = "PIX3HG72QnI4tLE1OTue"

robokassa = Robokassa(
    merchant_login=MERCHANT_LOGIN,
    password1=ROBOKASSA_PASS_1,
    password2=ROBOKASSA_PASS_2,
    algorithm=HashAlgorithm.sha256,
)


async def create_payment_robokassa(price, email, num_of_chapter, order_code, order_id, user_id):
    formatted_chapter = f'ch_{num_of_chapter}'
    description = "Доступ"

    # sno, который ты хочешь использовать
    sno = "usn_income"

    # исходные позиции
    raw_items = [
        {
            "Name": "Доступ",
            "Quantity": 1,
            "Sum": price,
            "PaymentMethod": "full_prepayment",
            "PaymentObject": "service",
            "Tax": "vat0"
        }
    ]

    # формируем финальный receipt
    receipt = {
        "Sno": sno,
        "Items": raw_items
    }

    # вызываем библиотечную функцию
    response = await robokassa.generate_protected_payment_link(
        merchant_comments="no comment",
        description=description,
        invoice_type=InvoiceType.ONE_TIME,
        email=email,
        inv_id=order_code,
        out_sum=price,
        receipt=receipt,
        user_id=user_id,
        formatted_chapter=formatted_chapter,
        order_id=order_id
    )
    print(response.url)
    return response.url

if __name__ == "__main__":
    asyncio.run(
        create_payment_robokassa(
            price=990,
            email="matvey@google.com",
            num_of_chapter=1,
            order_code=165226,
            order_id=789,
            user_id=42
        )
    )