# Рекуррентные платежи

Библиотека поддерживает выполнение рекуррентных платежей через эндпоинт `https://auth.robokassa.ru/Merchant/Recurring`.

## Метод execute_recurring_payment()

Выполняет рекуррентный платеж, используя ID предыдущего успешного платежа.

```python
await robokassa.execute_recurring_payment(
    previous_inv_id=12345,
    out_sum=100.0,
    inv_id=67890,
    description="Monthly subscription payment",
    email="customer@example.com",
    user_ip="192.168.1.1",
    shp_subscription_id="sub_123"
)
```

## Параметры

| Наименование | Описание | Тип | Обязательный |
|:-------------|:---------|:----|:-------------|
| `previous_inv_id` | ID предыдущего успешного платежа | `int` | ✅ |
| `out_sum` | Сумма к списанию | `Union[float, int]` | ✅ |
| `inv_id` | Новый ID счета для рекуррентного платежа | `int` | ✅ |
| `receipt` | Данные чека для фискализации | `Optional[dict]` | ❌ |
| `description` | Описание платежа | `Optional[str]` | ❌ |
| `email` | Email клиента | `Optional[str]` | ❌ |
| `user_ip` | IP адрес клиента | `Optional[str]` | ❌ |
| `**kwargs` | Дополнительные параметры с префиксом `shp_` | `dict` | ❌ |

## Возвращаемое значение

Возвращает объект `RobokassaResponse` с информацией о выполненном платеже.

## Пример использования

```python
import asyncio
from robokassa import Robokassa
from robokassa.hash import HashAlgorithm

async def execute_recurring_payment():
    robokassa = Robokassa(
        merchant_login="your_login",
        password1="your_password1",
        password2="your_password2",
        algorithm=HashAlgorithm.md5,
        is_test=True,
    )
    
    try:
        result = await robokassa.execute_recurring_payment(
            previous_inv_id=12345,
            out_sum=100.0,
            inv_id=67890,
            description="Monthly subscription",
            email="customer@example.com",
            shp_subscription_id="sub_123"
        )
        
        print(f"Payment executed: {result.url}")
        print(f"Amount: {result.params.out_sum}")
        
    except Exception as e:
        print(f"Error: {e}")

# Запуск
asyncio.run(execute_recurring_payment())
```

## Обработка ошибок

Метод может выбросить следующие исключения:

- `RobokassaInterfaceError` - при ошибке выполнения платежа
- `Exception` - при других ошибках (HTTP ошибки, проблемы с сетью и т.д.)

## Важные замечания

1. **PreviousInvoiceID** должен быть ID успешного платежа, который был выполнен с параметром `recurring=True`
2. Рекуррентные платежи работают только с теми же реквизитами, что и исходный платеж
3. Сумма может отличаться от исходного платежа
4. Для тестовых платежей используйте `is_test=True`
5. Все дополнительные параметры должны иметь префикс `shp_`

## Сравнение с generate_subscription_link()

| Метод | Описание | Возвращает |
|:------|:---------|:-----------|
| `generate_subscription_link()` | Создает ссылку для рекуррентного платежа | URL для перехода |
| `execute_recurring_payment()` | Выполняет рекуррентный платеж напрямую | Результат выполнения |

Метод `execute_recurring_payment()` является более удобным, так как выполняет платеж напрямую без необходимости перехода по ссылке. 