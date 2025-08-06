# Настройка логики рекуррентных платежей с тремя попытками

## Что было реализовано

Система теперь поддерживает логику рекуррентных платежей с тремя попытками списания:

1. **Первая попытка** (например, 10 августа) - обычное списание
2. **Вторая попытка** (например, 11 августа) - повторное списание + уведомление
3. **Третья попытка** (например, 12 августа) - последнее списание + удаление из канала

### 🔥 Важное исправление: Правильное получение previous_inv_id

**Проблема:** Раньше для рекуррентных платежей использовался `previous_inv_id` из последнего заказа.

**Решение:** Теперь используется `previous_inv_id` из самого первого платежа, который активировал подписку.

Это критически важно для корректной работы рекуррентных платежей в Robokassa.

## Шаги для применения изменений

### 1. Обновление базы данных

Выполните SQL-скрипт для добавления новых полей:

```bash
psql -h your_host -U your_user -d your_database -f fix_tables.sql
```

Или выполните команды вручную:

```sql
-- Добавление полей для отслеживания попыток списания
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS charge_attempts INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_charge_attempt TIMESTAMPTZ;

-- Обновление существующих записей
UPDATE subscriptions SET charge_attempts = 0 WHERE charge_attempts IS NULL;
```

### 2. Обновление кода

Все необходимые изменения уже внесены в файлы:

- ✅ `src/postgresdb.py` - добавлены новые методы, включая `get_first_payment_for_subscription()`
- ✅ `src/subscription_jobs.py` - модифицирована логика списания с правильным получением `previous_inv_id`
- ✅ `fix_tables.sql` - SQL-скрипт для БД

### 3. Тестирование

Запустите тестовый скрипт для проверки:

```bash
cd src
python test_subscription_logic.py
```

### 4. Перезапуск бота

После применения изменений перезапустите бота:

```bash
# Если используете Docker
docker-compose restart

# Или если запускаете напрямую
python src/__main__.py
```

## Проверка работы

### Логи для мониторинга

Система будет логировать следующие события:

```
✅ Рекуррентное списание отправлено для пользователя 123456 (попытка 1)
⚠️ Не удалось списать оплату за подписку. Это последняя попытка.
⚠️ Превышено количество попыток списания для подписки 1
✅ Пользователь 123456 удален из канала из-за превышения попыток списания
❌ Не удалось получить первый платеж для подписки 1
```

### Проверка в базе данных

```sql
-- Проверка попыток списания
SELECT subscription_id, user_id, charge_attempts, last_charge_attempt, status 
FROM subscriptions 
WHERE charge_attempts > 0;

-- Проверка подписок с истекшим сроком
SELECT subscription_id, user_id, charge_attempts, status 
FROM subscriptions 
WHERE status = 'expired' AND charge_attempts >= 3;

-- Проверка первого платежа для подписки
SELECT s.subscription_id, s.user_id, o.order_code as first_payment_inv_id
FROM subscriptions s
JOIN orders o ON s.order_id = o.order_id
WHERE s.subscription_id = 1;
```

## Уведомления пользователям

### При неудачном списании (попытки 1-2):
```
⚠️ Не удалось списать оплату за подписку. Это последняя попытка. 
Пожалуйста, проверьте данные карты или обратитесь в поддержку.
```

### При превышении попыток (попытка 3):
```
❌ Ваша подписка была приостановлена из-за неудачных попыток списания. 
Для восстановления доступа обратитесь в поддержку.
```

### При успешном списании:
```
✅ Ваша подписка успешно продлена!
```

## Настройка интервалов

По умолчанию интервал между попытками составляет **1 день**. 

Для изменения интервала отредактируйте в `src/subscription_jobs.py`:

```python
# Строка 95: изменить timedelta(days=1) на нужный интервал
when=timedelta(days=1)  # Например, timedelta(hours=12) для 12 часов
```

## Откат изменений

Если потребуется откатить изменения:

1. **Откат кода**: восстановите предыдущие версии файлов из git
2. **Откат БД**: 
   ```sql
   ALTER TABLE subscriptions DROP COLUMN IF EXISTS charge_attempts;
   ALTER TABLE subscriptions DROP COLUMN IF EXISTS last_charge_attempt;
   ```

## Поддержка

При возникновении проблем:

1. Проверьте логи бота на наличие ошибок
2. Убедитесь, что SQL-скрипт выполнен успешно
3. Проверьте подключение к базе данных
4. Запустите тестовый скрипт для диагностики
5. Проверьте, что первый платеж подписки существует в базе данных

## Дополнительные возможности

### Мониторинг через SQL

```sql
-- Статистика попыток списания
SELECT 
    COUNT(*) as total_subscriptions,
    SUM(CASE WHEN charge_attempts = 0 THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN charge_attempts > 0 AND charge_attempts < 3 THEN 1 ELSE 0 END) as retrying,
    SUM(CASE WHEN charge_attempts >= 3 THEN 1 ELSE 0 END) as failed
FROM subscriptions 
WHERE status = 'active';

-- Проверка первого платежа для всех подписок
SELECT 
    s.subscription_id,
    s.user_id,
    o.order_code as first_payment_inv_id,
    s.charge_attempts
FROM subscriptions s
JOIN orders o ON s.order_id = o.order_id
WHERE s.status = 'active';
```

### Автоматическое восстановление

Для автоматического восстановления подписок после исправления проблем с картой:

```sql
-- Сброс попыток для всех активных подписок
UPDATE subscriptions 
SET charge_attempts = 0, last_charge_attempt = NULL 
WHERE status = 'active' AND charge_attempts > 0;
```

## Технические детали

### Логика получения previous_inv_id

```python
# Получаем первый платеж для рекуррентного списания
first_payment_inv_id = pdb.get_first_payment_for_subscription(subscription_id)
if not first_payment_inv_id:
    logger.error(f"❌ Не удалось получить первый платеж для подписки {subscription_id}")
    return

# Используем первый платеж для рекуррентного списания
await payment.create_recurring_payment_robokassa(
    # ... другие параметры ...
    previous_inv_id=first_payment_inv_id  # Первый платеж подписки
)
```

Это обеспечивает, что все рекуррентные платежи ссылаются на один и тот же первоначальный платеж, что является требованием Robokassa для рекуррентных списаний. 