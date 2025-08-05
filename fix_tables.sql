-- Исправление таблицы subscriptions - добавление next_payment_date
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS next_payment_date TIMESTAMPTZ;

-- Исправление таблицы payments - изменение foreign key на orders
ALTER TABLE payments DROP CONSTRAINT IF EXISTS payments_order_id_fkey;
ALTER TABLE payments ADD CONSTRAINT payments_order_id_fkey 
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE;

-- Исправление таблицы manual_access - изменение типа created_at
ALTER TABLE manual_access ALTER COLUMN created_at TYPE TIMESTAMPTZ;