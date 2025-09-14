import logging
from datetime import datetime, timedelta, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from setup import pdb
import payment
import config
import other_func
import keyboard
from postgresdb import add_one_month_safe

logger = logging.getLogger(__name__)


async def charge_subscription_job(context):
    """
    Задача на повторное списание подписки.
    Отправляет рекуррентный платеж и планирует kick задачу для проверки результата.
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

        # Получаем количество попыток списания
        charge_attempts = pdb.get_charge_attempts(subscription_id)

        # Проверяем, не превышено ли количество попыток
        if charge_attempts >= 3:
            logger.warning(f"⚠️ Превышено количество попыток списания для подписки {subscription_id}")
            # Удаляем пользователя из канала
            pdb.remove_user_from_channel(user_id)

            kick_job_name = f"kick_{subscription_id}_{user_id}"
            kick_time = subscription['end_date']

            # Проверяем, что время еще не наступило
            now = datetime.now(timezone.utc)
            if kick_time <= now:
                context.job_queue.run_once(
                    kick_subscription_job,
                    when=timedelta(seconds=1),
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=kick_job_name
                )
            return

        # Создаем новый заказ для повторного списания
        new_order_code = other_func.generate_order_number()
        new_order_id = pdb.create_order(user_id=user_id, order_code=new_order_code)

        # Получаем email из старого заказа для нового
        old_order_data = pdb.get_order_by_id(subscription['order_id'])
        if old_order_data and old_order_data['email']:
            pdb.update_order_email(new_order_id, old_order_data['email'])

        # Получаем первый платеж для рекуррентного списания
        first_payment_inv_id = pdb.get_first_payment_for_subscription(subscription_id)
        if not first_payment_inv_id:
            logger.error(f"❌ Не удалось получить первый платеж для подписки {subscription_id}")
            return

        # Создаем повторный платеж с новым заказом
        course = config.courses.get('course')

        price = course['price']

        # # Определяем цену в зависимости от типа подписки
        # if subscription['subscription_type'] == 'test':
        #     if user_id == 7768888247 or user_id == 5738018066:
        #         price = 2
        #     else:
        #         # Для тестовых подписок списываем полную цену курса
        #         price = course['price']  # 990 рублей
        # elif user_id == 7768888247 or user_id == 5738018066:
        #     price = 2
        # else:
        #     price = course['price']

        # Создаем рекуррентный платеж
        await payment.create_recurring_payment_robokassa(
            price=price,
            email=old_order_data['email'] if old_order_data else '',
            num_of_chapter='course',
            order_code=new_order_code,
            order_id=new_order_id,
            user_id=user_id,
            previous_inv_id=first_payment_inv_id  # Используем первый платеж
        )
        logger.info(f"✅ Рекуррентное списание отправлено для пользователя {user_id} (попытка {charge_attempts + 1})")

        # Планируем задачу на проверку через 15 минут
        kick_job_name = f"kick_{subscription_id}_{user_id}"
        kick_time = datetime.now(timezone.utc) + timedelta(minutes=15)

        # Создаем задачу в job_queue
        context.job_queue.run_once(
            kick_subscription_job,
            when=timedelta(minutes=15),
            data={'user_id': user_id, 'subscription_id': subscription_id, 'order_id': new_order_id},
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
            job_id = pdb.get_pending_job_by_subscription_and_type(subscription_id, 'charge')
            if job_id:
                pdb.mark_job_done(job_id)
                logger.info(f"✅ Задача charge {job_id} отмечена как выполненная в БД")
        except Exception as e:
            logger.error(f"❌ Ошибка при отметке задачи charge в БД: {e}")


async def kick_subscription_job(context):
    """
    Задача на проверку результата платежа.
    Проверяет успешность платежа и либо продлевает подписку, 
    либо планирует следующую попытку списания, либо удаляет из канала.
    """
    job = context.job
    user_id = job.data['user_id']
    subscription_id = job.data['subscription_id']
    order_id = job.data.get('order_id')  # ID заказа для проверки платежа

    try:
        # Получаем подписку и проверяем её статус
        subscription = pdb.get_subscription_by_id(subscription_id)
        if not subscription:
            logger.warning(f"⚠️ Подписка {subscription_id} не найдена")
            return

        # Проверяем статус подписки
        if subscription['status'] == 'cancelled':
            # Проверяем, есть ли у пользователя другая активная подписка
            if pdb.has_active_subscription(user_id):
                logger.info(f"✅ Пользователь {user_id} имеет активную подписку, не удаляем из канала")
                return
            else:
                # Подписка отменена и нет активной подписки - удаляем из канала
                pdb.remove_user_from_channel(user_id)

                # Реально баним пользователя из канала
                try:
                    channel_id = config.courses.get('course', {}).get('channel_id')
                    group_id = config.courses.get('course', {}).get('group_id')
                    if channel_id:
                        await context.bot.ban_chat_member(
                            chat_id=channel_id,
                            user_id=user_id
                        )
                        await context.bot.unban_chat_member(
                            chat_id=channel_id,
                            user_id=user_id,
                            only_if_banned=True  # Снимаем бан только если пользователь действительно забанен
                        )
                        logger.info(f"✅ Пользователь {user_id} забанен в канале {channel_id} (отмененная подписка)")
                    else:
                        logger.error(f"❌ Не удалось получить channel_id для бана пользователя {user_id}")
                    if group_id:
                        await context.bot.ban_chat_member(
                            chat_id=group_id,
                            user_id=user_id
                        )
                        # Сразу снимаем бан, чтобы пользователь мог вернуться в будущем
                        await context.bot.unban_chat_member(
                            chat_id=group_id,
                            user_id=user_id,
                            only_if_banned=True  # Снимаем бан только если пользователь действительно забанен
                        )
                        logger.info(f"✅ Пользователь {user_id} забанен в чате {group_id}")
                    else:
                        logger.error(f"❌ Не удалось получить group_id для бана пользователя {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при бане пользователя {user_id} из канала: {e}")

                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Ваша подписка была отменена. Для оформления новой подписки нажмите кнопку ниже.",
                    reply_markup=keyboard.renew_subscription_button_markup()
                )
                logger.info(f"✅ Пользователь {user_id} удален из канала (отмененная подписка)")
                return

        # Проверяем, был ли успешный платеж
        payment_successful = False
        if order_id:
            payment_data = pdb.get_payment_by_order_id(order_id)
            payment_successful = payment_data is not None
            logger.info(f"🔍 Проверка платежа для заказа {order_id}: {'успешен' if payment_successful else 'не найден'}")

        if payment_successful:
            # Платеж успешен - продлеваем подписку
            pdb.reset_charge_attempts(subscription_id)
            pdb.extend_subscription(subscription_id)

            # Получаем обновленные данные подписки
            subscription = pdb.get_subscription_by_id(subscription_id)
            if subscription and subscription['subscription_type'] == 'test':
                # Для тестовых подписок после успешного рекуррентного платежа
                # меняем тип на обычную подписку и планируем месячные списания
                pdb.update_subscription_type(subscription_id, 'regular')
                logger.info(f"🔄 Тестовая подписка {subscription_id} преобразована в обычную после успешного платежа")

                # Планируем следующее списание через месяц (как для обычной подписки)
                schedule_subscription_jobs(context, user_id, subscription_id)
            else:
                # Для обычных подписок - планируем следующее списание через месяц
                schedule_subscription_jobs(context, user_id, subscription_id)

            logger.info(f"✅ Подписка {subscription_id} продлена после успешного платежа")
        else:
            # Платеж не найден - обрабатываем неудачу
            charge_attempts = pdb.get_charge_attempts(subscription_id)

            if charge_attempts >= 3:
                # Превышено количество попыток - удаляем из канала
                pdb.remove_user_from_channel(user_id)

                # Реально баним пользователя из канала
                try:
                    # Получаем channel_id из конфигурации
                    channel_id = config.courses.get('course', {}).get('channel_id')
                    group_id = config.courses.get('course', {}).get('group_id')
                    if channel_id:
                        await context.bot.ban_chat_member(
                            chat_id=channel_id,
                            user_id=user_id
                        )
                        # Сразу снимаем бан, чтобы пользователь мог вернуться в будущем
                        await context.bot.unban_chat_member(
                            chat_id=channel_id,
                            user_id=user_id,
                            only_if_banned=True  # Снимаем бан только если пользователь действительно забанен
                        )
                        logger.info(f"✅ Пользователь {user_id} забанен в канале {channel_id}")
                    else:
                        logger.error(f"❌ Не удалось получить channel_id для бана пользователя {user_id}")
                    if group_id:
                        await context.bot.ban_chat_member(
                            chat_id=group_id,
                            user_id=user_id
                        )
                        # Сразу снимаем бан, чтобы пользователь мог вернуться в будущем
                        await context.bot.unban_chat_member(
                            chat_id=group_id,
                            user_id=user_id,
                            only_if_banned=True  # Снимаем бан только если пользователь действительно забанен
                        )
                        logger.info(f"✅ Пользователь {user_id} забанен в чате {group_id}")
                    else:
                        logger.error(f"❌ Не удалось получить group_id для бана пользователя {user_id}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при бане пользователя {user_id} из канала: {e}")

                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ Ваша подписка была приостановлена из-за неудачных попыток списания. Для оформления подписки заново нажмите кнопку ниже.",
                    reply_markup=keyboard.renew_subscription_button_markup()
                )
                logger.info(f"✅ Пользователь {user_id} забанен в канале на 1 секунду из-за превышения попыток списания")
            else:
                # Если это 2-я попытка, отправляем уведомление
                if charge_attempts == 2:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⚠️ Не удалось списать оплату за подписку. Это 2 попытка из 3. Пожалуйста, проверьте баланс карты, с которой было прошлое списание, или оформите подписку заново с другой картой.",
                        reply_markup=keyboard.renew_subscription_button_markup()
                    )

                # Увеличиваем счетчик попыток
                pdb.increment_charge_attempts(subscription_id)

                # Планируем следующую попытку списания через день
                next_attempt_time = datetime.now(timezone.utc) + timedelta(days=1)
                charge_job_name = f"charge_{subscription_id}_{user_id}"

                context.job_queue.run_once(
                    charge_subscription_job,
                    when=timedelta(days=1),
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=charge_job_name
                )

                # Дублируем в БД для резерва
                try:
                    db_job_id = pdb.schedule_job(user_id, subscription_id, 'charge', next_attempt_time)
                    logger.info(
                        f"✅ Создана задача {charge_job_name} (БД ID: {db_job_id}) на следующую попытку списания через день")
                except Exception as e:
                    logger.error(f"❌ Ошибка при создании задачи в БД: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке kick job: {e}")
    finally:
        # Отмечаем задачу как выполненную в БД
        try:
            # Находим задачу в БД по subscription_id и job_type
            job_id = pdb.get_pending_job_by_subscription_and_type(subscription_id, 'kick')
            if job_id:
                pdb.mark_job_done(job_id)
                logger.info(f"✅ Задача {job_id} отмечена как выполненная в БД")
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

            existing_job_id = pdb.get_pending_job_by_subscription_and_type(subscription_id, 'charge')

            charge_job_name = f"charge_{subscription_id}_{user_id}"
            existing_jobs = context.job_queue.get_jobs_by_name(charge_job_name)

            now = datetime.now(timezone.utc)

            if existing_job_id and not existing_jobs:
                logger.info(f"🔄 Восстанавливаем задачу для подписки {subscription_id} из БД")
                time_until_payment = next_payment_date - now

                if time_until_payment.total_seconds() > 0:
                    context.job_queue.run_once(
                        charge_subscription_job,
                        when=time_until_payment,
                        data={'user_id': user_id, 'subscription_id': subscription_id},
                        name=charge_job_name
                    )
                    logger.info(
                        f"✅ Восстановлена задача {charge_job_name} на {next_payment_date.strftime('%d.%m.%Y %H:%M')}")
                else:
                    urgent_time = now + timedelta(minutes=1)
                    context.job_queue.run_once(
                        charge_subscription_job,
                        when=timedelta(minutes=1),
                        data={'user_id': user_id, 'subscription_id': subscription_id},
                        name=charge_job_name
                    )
                    logger.info(f"✅ Восстановлена срочная задача {charge_job_name} - платеж просрочен")
                continue

            if existing_job_id and existing_jobs:
                logger.info(f"ℹ️ Задача для подписки {subscription_id} уже существует в БД и job_queue, пропускаем")
                continue

            if not existing_job_id and not existing_jobs:
                logger.info(f"🆕 Создаем новую задачу для подписки {subscription_id}")
                time_until_payment = next_payment_date - now

                if time_until_payment.total_seconds() > 0:
                    context.job_queue.run_once(
                        charge_subscription_job,
                        when=time_until_payment,
                        data={'user_id': user_id, 'subscription_id': subscription_id},
                        name=charge_job_name
                    )
                    try:
                        db_job_id = pdb.schedule_job(user_id, subscription_id, 'charge', next_payment_date)
                        logger.info(
                            f"✅ Создана задача {charge_job_name} (БД ID: {db_job_id}) на {next_payment_date.strftime('%d.%m.%Y %H:%M')}")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при создании задачи в БД: {e}")
                else:
                    urgent_time = now + timedelta(minutes=1)
                    context.job_queue.run_once(
                        charge_subscription_job,
                        when=timedelta(minutes=1),
                        data={'user_id': user_id, 'subscription_id': subscription_id},
                        name=charge_job_name
                    )
                    try:
                        db_job_id = pdb.schedule_job(user_id, subscription_id, 'charge', urgent_time)
                        logger.info(
                            f"✅ Создана срочная задача {charge_job_name} (БД ID: {db_job_id}) - платеж просрочен")
                    except Exception as e:
                        logger.error(f"❌ Ошибка при создании срочной задачи в БД: {e}")

        # === ДОБАВЛЕНО: ставим kick для отменённых и уже истёкших подписок ===
        cancelled_expired_subscriptions = pdb.get_cancelled_and_expired_subscriptions()

        for subscription in cancelled_expired_subscriptions:
            user_id = subscription['user_id']
            subscription_id = subscription['subscription_id']

            existing_kick_job_id = pdb.get_pending_job_by_subscription_and_type(subscription_id, 'kick')

            kick_job_name = f"kick_{subscription_id}_{user_id}"
            existing_kick_jobs = context.job_queue.get_jobs_by_name(kick_job_name)

            now = datetime.now(timezone.utc)

            # «Ближайшее время»: через 5 секунд (можно вернуть 1 минуту, если так удобнее)
            kick_delay = timedelta(seconds=5)
            kick_time = now + kick_delay

            if existing_kick_job_id and existing_kick_jobs:
                logger.info(
                    f"ℹ️ Kick-задача для подписки {subscription_id} уже существует в БД и job_queue, пропускаем")
                continue

            if existing_kick_job_id and not existing_kick_jobs:
                logger.info(f"🔄 Восстанавливаем kick-задачу для подписки {subscription_id} из БД")
                context.job_queue.run_once(
                    kick_subscription_job,
                    when=kick_delay,
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=kick_job_name
                )
                logger.info(f"✅ Восстановлена kick-задача {kick_job_name} на немедленное выполнение")
                continue

            if not existing_kick_job_id and not existing_kick_jobs:
                logger.info(f"🆕 Создаем kick-задачу для подписки {subscription_id}")
                context.job_queue.run_once(
                    kick_subscription_job,
                    when=kick_delay,
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=kick_job_name
                )
                try:
                    db_job_id = pdb.schedule_job(user_id, subscription_id, 'kick', kick_time)
                    logger.info(f"✅ Создана kick-задача {kick_job_name} (БД ID: {db_job_id})")
                except Exception as e:
                    logger.error(f"❌ Ошибка при создании kick-задачи в БД: {e}")

        # ⬇️ Перенесённый итоговый лог (после блока kick)
        logger.info(f"✅ Синхронизация завершена. Обработано {len(active_subscriptions)} активных подписок, "
                    f"kick-проверок: {len(cancelled_expired_subscriptions)}")

    except Exception as e:
        logger.error(f"❌ Ошибка при синхронизации job_queue: {e}")


def schedule_subscription_jobs(context, user_id: int, subscription_id: int):
    """
    Планирует задачи для подписки.
    
    :param context: Контекст бота
    :param user_id: Telegram user ID
    :param subscription_id: ID подписки
    """
    try:
        # pdb.reset_charge_attempts(subscription_id)

        # Получаем данные подписки для определения типа
        subscription = pdb.get_subscription_by_id(subscription_id)
        if not subscription:
            logger.error(f"❌ Подписка {subscription_id} не найдена")
            return

        # Вычисляем дату следующего платежа в зависимости от типа подписки
        now = datetime.now(timezone.utc)

        if subscription['subscription_type'] == 'test':
            # Для тестовых подписок - через 48 часов
            next_payment_date = now + timedelta(hours=48)
            time_until_payment = timedelta(hours=48)
            logger.info(f"📅 Тестовая подписка {subscription_id}: следующий платеж через 48 часов")
        else:
            # Для обычных подписок - через месяц
            next_payment_date = add_one_month_safe(now)
            time_until_payment = next_payment_date - now
            logger.info(f"📅 Обычная подписка {subscription_id}: следующий платеж через месяц")

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
            db_job_id = pdb.schedule_job(user_id, subscription_id, 'charge', next_payment_date)
            logger.info(
                f"✅ Создана задача {charge_job_name} (БД ID: {db_job_id}) на {next_payment_date.strftime('%d.%m.%Y %H:%M')}")
        except Exception as e:
            logger.error(f"❌ Ошибка при создании задачи в БД: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка при планировании задач подписки: {e}")


def cancel_subscription_jobs(context, subscription_id: int, user_id: int):
    """
    Отменяет задачи для подписки и планирует kick на дату истечения.
    
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

        # Получаем дату истечения подписки
        subscription = pdb.get_subscription_by_id(subscription_id)
        if subscription and subscription['end_date']:
            # Планируем kick задачу на дату истечения подписки
            kick_job_name = f"kick_{subscription_id}_{user_id}"
            kick_time = subscription['end_date']

            # Проверяем, что время еще не наступило
            now = datetime.now(timezone.utc)
            if kick_time > now:
                context.job_queue.run_once(
                    kick_subscription_job,
                    when=kick_time - now,
                    data={'user_id': user_id, 'subscription_id': subscription_id},
                    name=kick_job_name
                )

                # Дублируем в БД для резерва
                try:
                    db_job_id = pdb.schedule_job(user_id, subscription_id, 'kick', kick_time)
                    logger.info(
                        f"✅ Создана задача {kick_job_name} (БД ID: {db_job_id}) на дату истечения {kick_time.strftime('%d.%m.%Y %H:%M')}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при создании задачи в БД: {e}")
            else:
                logger.info(f"ℹ️ Дата истечения подписки {subscription_id} уже наступила")

    except Exception as e:
        logger.error(f"❌ Ошибка при отмене задач подписки: {e}")


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
