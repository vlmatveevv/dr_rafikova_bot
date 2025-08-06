-- Исправление таблицы subscriptions - добавление next_payment_date
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS next_payment_date TIMESTAMPTZ;

-- Добавление полей для отслеживания попыток списания
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS charge_attempts INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS last_charge_attempt TIMESTAMPTZ;

-- Обновление существующих записей - установка значений по умолчанию
UPDATE subscriptions SET charge_attempts = 0 WHERE charge_attempts IS NULL;

-- Исправление таблицы payments - изменение foreign key на orders
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_order_id_fkey;
ALTER TABLE payments ADD CONSTRAINT payments_order_id_fkey 
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE;

-- Исправление таблицы manual_access - изменение типа created_at
ALTER TABLE manual_access ALTER COLUMN created_at TYPE TIMESTAMPTZ;