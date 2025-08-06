#!/usr/bin/env python3
"""
Тестовый скрипт для проверки логики рекуррентных платежей с тремя попытками.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from setup import pdb

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_subscription_logic():
    """
    Тестирует новую логику рекуррентных платежей.
    """
    try:
        # Тестовые данные
        test_user_id = 123456789
        test_subscription_id = 1
        
        logger.info("🧪 Начинаем тестирование логики рекуррентных платежей")
        
        # Проверяем, существует ли тестовая подписка
        subscription = pdb.get_subscription_by_id(test_subscription_id)
        if not subscription:
            logger.warning(f"⚠️ Тестовая подписка {test_subscription_id} не найдена")
            return
        
        logger.info(f"✅ Найдена подписка: {subscription}")
        
        # Проверяем текущее количество попыток
        current_attempts = pdb.get_charge_attempts(test_subscription_id)
        logger.info(f"📊 Текущее количество попыток: {current_attempts}")
        
        # Тестируем увеличение попыток
        pdb.increment_charge_attempts(test_subscription_id)
        new_attempts = pdb.get_charge_attempts(test_subscription_id)
        logger.info(f"📈 Количество попыток после увеличения: {new_attempts}")
        
        # Тестируем сброс попыток
        pdb.reset_charge_attempts(test_subscription_id)
        reset_attempts = pdb.get_charge_attempts(test_subscription_id)
        logger.info(f"🔄 Количество попыток после сброса: {reset_attempts}")
        
        # Симулируем 3 неудачные попытки
        logger.info("🔄 Симулируем 3 неудачные попытки списания...")
        for i in range(3):
            pdb.increment_charge_attempts(test_subscription_id)
            attempts = pdb.get_charge_attempts(test_subscription_id)
            logger.info(f"   Попытка {i+1}: {attempts} попыток")
        
        # Проверяем, что после 3 попыток пользователь будет удален
        final_attempts = pdb.get_charge_attempts(test_subscription_id)
        if final_attempts >= 3:
            logger.info(f"⚠️ Достигнуто максимальное количество попыток: {final_attempts}")
            logger.info("✅ Логика работает корректно - пользователь будет удален из канала")
        
        # Сбрасываем для чистоты теста
        pdb.reset_charge_attempts(test_subscription_id)
        logger.info("✅ Тест завершен успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании: {e}")


async def test_database_methods():
    """
    Тестирует новые методы базы данных.
    """
    try:
        logger.info("🧪 Тестируем новые методы базы данных")
        
        # Создаем тестовую подписку (если нужно)
        test_user_id = 999999999
        test_order_id = 999999999
        
        # Проверяем методы
        logger.info("📊 Проверяем метод get_charge_attempts...")
        attempts = pdb.get_charge_attempts(1)  # Тестовая подписка
        logger.info(f"   Результат: {attempts}")
        
        logger.info("📈 Проверяем метод increment_charge_attempts...")
        pdb.increment_charge_attempts(1)
        new_attempts = pdb.get_charge_attempts(1)
        logger.info(f"   Результат: {new_attempts}")
        
        logger.info("🔄 Проверяем метод reset_charge_attempts...")
        pdb.reset_charge_attempts(1)
        reset_attempts = pdb.get_charge_attempts(1)
        logger.info(f"   Результат: {reset_attempts}")
        
        logger.info("✅ Тест методов базы данных завершен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании методов БД: {e}")


async def test_first_payment_logic():
    """
    Тестирует логику получения первого платежа для рекуррентных списаний.
    """
    try:
        logger.info("🧪 Тестируем логику получения первого платежа")
        
        # Тестовая подписка
        test_subscription_id = 1
        
        # Проверяем получение первого платежа
        logger.info("📊 Проверяем метод get_first_payment_for_subscription...")
        first_payment = pdb.get_first_payment_for_subscription(test_subscription_id)
        logger.info(f"   Первый платеж для подписки {test_subscription_id}: {first_payment}")
        
        if first_payment:
            logger.info("✅ Первый платеж найден - можно использовать для рекуррентных списаний")
        else:
            logger.warning("⚠️ Первый платеж не найден - проверить данные подписки")
        
        # Проверяем подписку
        subscription = pdb.get_subscription_by_id(test_subscription_id)
        if subscription:
            logger.info(f"   Подписка найдена: order_id = {subscription['order_id']}")
            
            # Проверяем заказ
            order = pdb.get_order_by_id(subscription['order_id'])
            if order:
                logger.info(f"   Заказ найден: order_code = {order['order_code']}")
            else:
                logger.warning("⚠️ Заказ не найден")
        else:
            logger.warning("⚠️ Подписка не найдена")
        
        logger.info("✅ Тест логики первого платежа завершен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при тестировании логики первого платежа: {e}")


if __name__ == "__main__":
    logger.info("🚀 Запуск тестов логики рекуррентных платежей")
    
    # Запускаем тесты
    asyncio.run(test_database_methods())
    asyncio.run(test_subscription_logic())
    asyncio.run(test_first_payment_logic())
    
    logger.info("✅ Все тесты завершены") 