-- Создание таблицы подписок
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    order_id INTEGER NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
    start_date TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMPTZ NOT NULL,
    next_payment_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_end_date ON subscriptions(end_date);

-- Создание таблицы scheduled_jobs (для совместимости, но теперь не используется)
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    job_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(subscription_id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (job_type IN ('charge', 'kick', 'notify')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
    run_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Создание индексов для scheduled_jobs
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status ON scheduled_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_run_at ON scheduled_jobs(run_at);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_subscription_id ON scheduled_jobs(subscription_id);

-- Комментарии к таблицам
COMMENT ON TABLE subscriptions IS 'Таблица подписок пользователей';
COMMENT ON TABLE scheduled_jobs IS 'Таблица запланированных задач (для совместимости)'; 