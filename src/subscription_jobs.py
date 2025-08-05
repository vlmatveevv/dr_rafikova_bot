import logging
from datetime import datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from setup import pdb
import payment
import config
import other_func

logger = logging.getLogger(__name__)


async def charge_subscription_job(context):
    """
    Задача на повторное списание подписки.
    """
    job = context.job
    user_id = job.data['user_id']
    subscription_id = job.data['subscription_id']
    
    try:
        # Получаем данные подписки
        subscription = pdb.get_subscription_by_id(subscription_id)
        if not subscription:
            logger.warning(f"⚠️ Подписка {subscription_id} не найдена")
            return

        # Проверяем статус подписки
        if subscription['status'] != 'active':
            logger.warning(f"⚠️ Подписка {subscription_id} неактивна (статус: {subscription['status']})")
            return

        # Создаем новый заказ для повторного списания
        new_order_code = other_func.generate_order_number()
        new_order_id = pdb.create_order(user_id=user_id, order_code=new_order_code)
        
        # Получаем email из старого заказа для нового
        old_order_data = pdb.get_order_by_id(subscription['order_id'])
        if old_order_data and old_order_data['email']:
            pdb.update_order_email(new_order_id, old_order_data['email'])
        
        # Создаем повторный платеж с новым заказом
        course = config.courses.get('course')
        if user_id == 146679674:
            price = 15
        else:
            price = course['price']

        await payment.create_recurring_payment_robokassa(
            price=price,
            email=old_order_data['email'] if old_order_data else '',
            num_of_chapter='course',
            order_code=new_order_code,
            order_id=new_order_id,
            user_id=user_id,
            previous_inv_id=old_order_data['order_code']
        )
        logger.info(f"✅ Рекуррентное списание отправлено для пользователя {user_id}")
        
        # Ставим задачу на проверку через 15 минут
        kick_job_name = f"kick_{subscription_id}_{user_id}"
        kick_time = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        # Создаем задачу в job_queue
        context.job_queue.run_once(
            kick_subscription_job,
            when=timedelta(minutes=15),
            data={'user_id': user_id, 'subscription_id': subscription_id},
            name=kick_job_name
        )
        
        # Дублируем в БД для резерва
        try:
            db_job_id = pdb.schedule_job(user_id, subscription_id, 'kick', kick_time)
            logger.info(f"✅ Создана задача {kick_job_name} (БД ID: {db_job_id}) на проверку через 15 минут")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании задачи в БД: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке charge job: {e}")
    finally:
        # Отмечаем задачу как выполненную в БД
        try:
            # Находим задачу в БД по subscription_id и job_type
            with pdb.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT job_id FROM scheduled_jobs 
                    WHERE subscription_id = %s AND job_type = 'charge' AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (subscription_id,))
                result = cursor.fetchone()
                if result:
                    pdb.mark_job_done(result[0])
                    logger.info(f"✅ Задача charge {result[0]} отмечена как выполненная в БД")
        except Exception as e:
            logger.error(f"❌ Ошибка при отметке задачи charge в БД: {e}")


async def kick_subscription_job(context):
    """
    Задача на исключение пользователя из канала.
    """
    job = context.job
    user_id = job.data['user_id']
    subscription_id = job.data['subscription_id']
    
    try:
        # Получаем подписку и проверяем её статус
        subscription = pdb.get_subscription_by_id(subscription_id)
        if not subscription:
            logger.warning(f"⚠️ Подписка {subscription_id} не найдена")
            return
            
        # Проверяем статус подписки
        if subscription['status'] == 'active':
            # Подписка активна, отменяем kick
            logger.info(f"✅ Подписка {subscription_id} активна, kick отменен")
            return

        # Подписка не продлена - отправляем уведомление с кнопкой оплаты
        keyboard = [[InlineKeyboardButton("💳 Оплатить", callback_data="pay_chapter")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text="🔄 Время продлить подписку! Нажмите кнопку ниже для оплаты:",
            reply_markup=reply_markup
        )
        
        logger.info(f"✅ Отправлено уведомление о необходимости оплаты пользователю {user_id}")
        
        # Обновляем статус подписки
        pdb.update_subscription_status(subscription_id, 'expired')

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке kick job: {e}")
    finally:
        # Отмечаем задачу как выполненную в БД
        try:
            # Находим задачу в БД по subscription_id и job_type
            now = datetime.now(timezone.utc)
            with pdb.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT job_id FROM scheduled_jobs 
                    WHERE subscription_id = %s AND job_type = 'kick' AND status = 'pending'
                    ORDER BY created_at DESC LIMIT 1
                """, (subscription_id,))
                result = cursor.fetchone()
                if result:
                    pdb.mark_job_done(result[0])
                    logger.info(f"✅ Задача {result[0]} отмечена как выполненная в БД")
        except Exception as e:
            logger.error(f"❌ Ошибка при отметке задачи в БД: {e}")


async def notify_subscription_job(context):
    """
    Задача на уведомление пользователя.
    """
    job = context.job
    user_id = job.data['user_id']
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="📢 Напоминание: ваша подписка скоро истечет!"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке notify job: {e}")


def schedule_subscription_jobs(context, user_id: int, subscription_id: int):
    """
    Планирует задачи для подписки.
    
    :param context: Контекст бота
    :param user_id: Telegram user ID
    :param subscription_id: ID подписки
    """
    try:
        # Вычисляем дату следующего платежа (то же число следующего месяца)
        now = datetime.now(timezone.utc)
        if now.month == 12:
            # Если декабрь, то следующий месяц - январь следующего года
            next_month = now.replace(year=now.year + 1, month=1)
        else:
            # Иначе просто увеличиваем месяц
            next_month = now.replace(month=now.month + 1)
        
        # Вычисляем время до следующего платежа
        time_until_payment = next_month - now
        
        # Задача на повторное списание
        charge_job_name = f"charge_{subscription_id}_{user_id}"
        
        # Создаем задачу в job_queue
        context.job_queue.run_once(
            charge_subscription_job,
            when=time_until_payment,
            data={'user_id': user_id, 'subscription_id': subscription_id},
            name=charge_job_name
        )
        
        # Дублируем в БД для резерва
        try:
            db_job_id = pdb.schedule_job(user_id, subscription_id, 'charge', next_month)
            logger.info(f"✅ Создана задача {charge_job_name} (БД ID: {db_job_id}) на {next_month.strftime('%d.%m.%Y')}")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании задачи в БД: {e}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при планировании задач подписки: {e}")


def cancel_subscription_jobs(context, subscription_id: int, user_id: int):
    """
    Отменяет задачи для подписки.
    
    :param context: Контекст бота
    :param subscription_id: ID подписки
    :param user_id: Telegram user ID
    """
    try:
        # Отменяем charge задачу
        charge_job_name = f"charge_{subscription_id}_{user_id}"
        current_jobs = context.job_queue.get_jobs_by_name(charge_job_name)
        for job in current_jobs:
            job.schedule_removal()
            logger.info(f"✅ Отменена задача {charge_job_name}")
        
        # Отменяем kick задачу
        kick_job_name = f"kick_{subscription_id}_{user_id}"
        current_jobs = context.job_queue.get_jobs_by_name(kick_job_name)
        for job in current_jobs:
            job.schedule_removal()
            logger.info(f"✅ Отменена задача {kick_job_name}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка при отмене задач подписки: {e}")


async def sync_job_queue_with_db(context):
    """
    Синхронизирует job_queue с БД - очищает и добавляет все задачи из БД.
    Запускается каждый день в 04:00.
    """
    try:
        logger.info("🔄 Начинаем синхронизацию job_queue с БД")
        
        # Удаляем только задачи подписок
        job_names_to_remove = []
        for job in context.job_queue.jobs():
            if job.name and (job.name.startswith("charge_") or job.name.startswith("kick_")):
                job.schedule_removal()
                job_names_to_remove.append(job.name)
        
        if job_names_to_remove:
            logger.info(f"✅ Удалены задачи подписок: {job_names_to_remove}")
        else:
            logger.info("ℹ️ Задач подписок для удаления не найдено")
        
        # Получаем все активные подписки
        active_subscriptions = pdb.get_all_active_subscriptions()
        
        for subscription in active_subscriptions:
            user_id = subscription['user_id']
            subscription_id = subscription['subscription_id']
            next_payment_date = subscription['next_payment_date']
            
            # Вычисляем время до следующего платежа
            from datetime import timezone
            now = datetime.now(timezone.utc)
            time_until_payment = next_payment_date - now
            
            # Если время еще не наступило, создаем задачу
            if time_until_payment.total_seconds() > 0:
                charge_job_name = f"charge_{subscription_id}_{user_id}"
                context.job_queue.run_once(
                    charge_subscription_job,
                    when=time_until_payment,
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=charge_job_name
                )
                logger.info(f"✅ Добавлена задача {charge_job_name} на {next_payment_date.strftime('%d.%m.%Y %H:%M')}")
            else:
                # Время уже наступило, создаем задачу на ближайшее время
                charge_job_name = f"charge_{subscription_id}_{user_id}"
                context.job_queue.run_once(
                    charge_subscription_job,
                    when=timedelta(minutes=1),  # Через минуту
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=charge_job_name
                )
                logger.info(f"✅ Добавлена срочная задача {charge_job_name} (платеж просрочен)")
        
        logger.info(f"✅ Синхронизация завершена. Добавлено {len(active_subscriptions)} задач")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при синхронизации job_queue: {e}")


def schedule_daily_sync(context):
    """
    Планирует ежедневную синхронизацию в 04:00.
    
    :param context: Контекст бота
    """
    try:
        # Вычисляем время до следующего 04:00
        now = datetime.now(timezone.utc)
        tomorrow_4am = now.replace(hour=4, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_until_4am = tomorrow_4am - now
        
        # Планируем синхронизацию
        context.job_queue.run_once(
            sync_job_queue_with_db,
            when=time_until_4am,
            data={},
            name="daily_sync"
        )
        
        # Планируем повторную синхронизацию через день
        context.job_queue.run_repeating(
            sync_job_queue_with_db,
            interval=timedelta(days=1),
            first=time_until_4am,
            data={},
            name="daily_sync_repeating"
        )
        
        logger.info(f"✅ Запланирована ежедневная синхронизация в 04:00")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при планировании ежедневной синхронизации: {e}") 