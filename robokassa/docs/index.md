# Начало работы

Библиотека **robokassa** представляет собой легковесное, производительное решение, не использующее посторонних зависимостей. При этом библиотека является асинхронной, это достигается за счёт использования **httpx**.

Эта документация, а также сама библиотека на являются продуктами «Robokassa». Весь функционал, который будет описан далее, разработан на основе официальной [документации](https://docs.robokassa.ru/).



## Установка

Для установки можно использовать любой пакетный менеджер:

* pip

```bash
pip install robokassa
```

* poetry

```bash
poetry add robokassa
```

## Пример использования

```py
from robokassa import HashAlgorithm, Robokassa

robokassa = Robokassa(
    merchant_login="my_login",
    password1="password",
    password2="password",
    is_test=False,
    algorithm=HashAlgorithm.md5,
)

my_link = robokassa.generate_open_payment_link(out_sum=1000, inv_id=0)

# Рекуррентные платежи

Для выполнения рекуррентных платежей используйте метод `execute_recurring_payment()`:

```python
import asyncio

async def execute_recurring():
    result = await robokassa.execute_recurring_payment(
        previous_inv_id=12345,  # ID предыдущего успешного платежа
        out_sum=100.0,          # Сумма к списанию
        inv_id=67890,           # Новый ID счета
        description="Monthly subscription"
    )
    print(f"Payment executed: {result.url}")

# Запуск
asyncio.run(execute_recurring())
```