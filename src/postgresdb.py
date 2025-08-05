import json
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values
import config
import logging
from datetime import datetime, timedelta

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        """
        Инициализация подключения к базе данных.
        """
        self.conn = psycopg2.connect(
            host=config.config_env['POSTGRES_HOST'],
            database=config.config_env['POSTGRES_DB'],
            user=config.config_env['POSTGRES_USER'],
            password=config.config_env['POSTGRES_PASSWORD']
        )

    def user_exists(self, user_id: int) -> bool:
        """
        Проверяет, существует ли пользователь в таблице users по user_id.

        :param user_id: Идентификатор пользователя.
        :return: True, если пользователь существует, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS(SELECT 1 FROM users WHERE user_id = %s)
                """, (user_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Ошибка при проверке существования пользователя: {e}")
            self.conn.rollback()  # Откат транзакции в случае ошибки
            return False

    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None) -> bool:
        """
        Добавляет нового пользователя в таблицу users.

        :param user_id: Идентификатор пользователя (обязательный).
        :param username: Имя пользователя (username) (необязательный).
        :param first_name: Имя пользователя (необязательный).
        :param last_name: Фамилия пользователя (необязательный).
        :return: True, если пользователь успешно добавлен, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, NOW(), NOW())
                """, (user_id, username, first_name, last_name))
                self.conn.commit()  # Подтверждение транзакции
                return True
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {e}")
            self.conn.rollback()  # Откат транзакции в случае ошибки
            return False

    def get_user_by_user_id(self, user_id: int):
        """
        Получение информации о пользователе по user_id.
        :param user_id: Telegram ID пользователя
        :return: Информация о платеже или None
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM users WHERE user_id = %s
                """, (user_id,))
                return cursor.fetchone()
        except Exception as e:
            self.conn.rollback()
            print(f"Error getting payment: {e}")
            return None

    def add_payment(self, amount: float, income_amount: float,
                    payment_method_type: str, order_id: int) -> bool:
        """
        Добавляет новый платёж в таблицу payments.

        :param amount: Сумма платежа.
        :param income_amount: Сумма после вычета комиссии.
        :param payment_method_type: Тип платёжного метода (например, 'card', 'sbp').
        :param order_id: ID заказа (внутренний).
        :return: True, если платёж успешно добавлен, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    INSERT INTO payments (
                        amount, income_amount, 
                        payment_method_type, order_id, created_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                """
                params = (
                    amount,
                    income_amount,
                    payment_method_type,
                    order_id
                )
                cursor.execute(query, params)
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Ошибка при добавлении платежа: {e}")
            self.conn.rollback()
            return False

    def get_payment_by_order_id(self, order_id: int):
        """
        Получение информации о платеже по order_id.
        :param order_id: Уникальный идентификатор заказа.
        :return: Словарь с данными платежа или None.
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM payments WHERE order_id = %s
                """, (order_id,))
                return cursor.fetchone()  # Возвращает словарь или None, если запись не найдена
        except Exception as e:
            self.conn.rollback()
            print(f"Ошибка при получении платежа по order_id {order_id}: {e}")
            return None

    # def payment_exists(self, external_payment_id: str) -> bool:
    #     """
    #     Проверка, существует ли платеж с данным payment_id в базе данных.
    #     :param external_payment_id: Уникальный ID платежа
    #     :return: True, если платеж существует, иначе False
    #     """
    #     try:
    #         with self.conn.cursor() as cursor:
    #             cursor.execute("""
    #                 SELECT EXISTS(SELECT 1 FROM payments WHERE external_payment_id = %s)
    #             """, (external_payment_id,))
    #             return cursor.fetchone()[0]
    #     except Exception as e:
    #         self.conn.rollback()
    #         print(f"Error checking payment existence: {e}")
    #         return False

    def payment_exists_by_order_code(self, order_code: int) -> bool:
        """
        Проверка, существует ли платеж, связанный с данным order_code (InvId).
        :param order_code: Код заказа (из Robokassa — InvId)
        :return: True, если платеж существует, иначе False
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1
                        FROM payments p
                        JOIN orders o ON p.order_id = o.order_id
                        WHERE o.order_code = %s
                    )
                """, (order_code,))
                return cursor.fetchone()[0]
        except Exception as e:
            self.conn.rollback()
            print(f"Error checking payment by order_code: {e}")
            return False

    def get_paid_courses_by_user(self, user_id: int) -> list:
        """
        Возвращает список курсов, которые пользователь успешно оплатил.
        У нас только один курс, поэтому возвращаем ['course'] если есть оплата.

        :param user_id: ID пользователя.
        :return: Список с одним элементом ['course'] или пустой список.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM orders o
                        JOIN payments p ON o.order_id = p.order_id
                        WHERE o.user_id = %s
                    )
                """
                cursor.execute(query, (user_id,))
                has_payment = cursor.fetchone()[0]
                return ['course'] if has_payment else []
        except Exception as e:
            print(f"Ошибка при получении курсов: {e}")
            return []

    def get_all_user_courses(self, user_id: int) -> list:
        """
        Возвращает список всех курсов, к которым у пользователя есть доступ:
        - оплаченные (в orders)
        - выданные вручную (manual_access)

        :param user_id: Telegram user ID
        :return: список с одним элементом ['course'] или пустой список
        """
        try:
            with self.conn.cursor() as cursor:
                # Проверяем оплату
                query_payment = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM orders o
                        JOIN payments p ON o.order_id = p.order_id
                        WHERE o.user_id = %s
                    )
                """
                cursor.execute(query_payment, (user_id,))
                has_payment = cursor.fetchone()[0]

                # Проверяем ручной доступ
                query_manual = """
                    SELECT EXISTS (
                        SELECT 1 FROM manual_access
                        WHERE user_id = %s AND course_chapter = 'course'
                    )
                """
                cursor.execute(query_manual, (user_id,))
                has_manual = cursor.fetchone()[0]

                return ['course'] if (has_payment or has_manual) else []
        except Exception as e:
            print(f"❌ Ошибка при получении всех доступных курсов: {e}")
            return []

    def get_not_bought_courses(self, user_id: int) -> list:
        """
        Возвращает список курсов, которые пользователь еще не купил.

        :param user_id: Telegram user ID
        :return: список с одним элементом ['course'] если не куплен, иначе пустой список
        """
        try:
            with self.conn.cursor() as cursor:
                # Проверяем, есть ли оплата или ручной доступ
                query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM orders o
                        JOIN payments p ON o.order_id = p.order_id
                        WHERE o.user_id = %s
                    )
                    OR EXISTS (
                        SELECT 1 FROM manual_access
                        WHERE user_id = %s AND course_chapter = 'course'
                    )
                """
                cursor.execute(query, (user_id, user_id))
                has_access = cursor.fetchone()[0]
                
                return ['course'] if not has_access else []
        except Exception as e:
            print(f"❌ Ошибка при получении некупленных курсов: {e}")
            return []

    def has_paid_course(self, user_id: int, course_chapter: str) -> bool:
        """
        Проверяет, оплатил ли пользователь курс.

        :param user_id: ID пользователя.
        :param course_chapter: Игнорируется, у нас только один курс.
        :return: True, если оплата есть, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM orders o
                        JOIN payments p ON o.order_id = p.order_id
                        WHERE o.user_id = %s
                    )
                """
                cursor.execute(query, (user_id,))
                result = cursor.fetchone()
                return result[0]  # True или False
        except Exception as e:
            print(f"Ошибка при проверке оплаты курса: {e}")
            return False

    def create_order(self, user_id: int, order_code: int) -> int:
        """
        Создает заказ в таблице orders и возвращает order_id.
        Email будет добавлен позже.

        :param user_id: Telegram user ID
        :param order_code: Уникальный код заказа
        :return: order_id
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    INSERT INTO orders (user_id, order_code)
                    VALUES (%s, %s)
                    RETURNING order_id;
                """
                cursor.execute(query, (user_id, order_code))
                order_id = cursor.fetchone()[0]
                self.conn.commit()
                return order_id
        except Exception as e:
            print(f"❌ Ошибка при создании заказа: {e}")
            self.conn.rollback()
            raise

    def update_email(self, order_code: int, email: str):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE orders
                    SET email = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = %s
                """, (email, order_code))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении email: {e}")
            self.conn.rollback()
            raise

    def update_agreed_offer(self, order_code: int, value: bool):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE orders
                    SET agreed_offer = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = %s
                """, (value, order_code))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении agreed_offer: {e}")
            self.conn.rollback()
            raise

    def update_agreed_privacy(self, order_code: int, value: bool):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE orders
                    SET agreed_privacy = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = %s
                """, (value, order_code))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении agreed_privacy: {e}")
            self.conn.rollback()
            raise

    def update_agreed_newsletter(self, order_code: int, value: bool):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE orders
                    SET agreed_newsletter = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = %s
                """, (value, order_code))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении agreed_newsletter: {e}")
            self.conn.rollback()
            raise

    def update_payment_message_id(self, order_code: int, message_id: int):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE orders
                    SET payment_message_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE order_code = %s
                """, (message_id, order_code))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении payment_message_id: {e}")
            self.conn.rollback()
            raise

    def get_payment_message_id(self, order_id: int) -> int | None:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT payment_message_id
                    FROM orders
                    WHERE order_id = %s
                """, (order_id,))
                result = cursor.fetchone()
                if result:
                    return result[0]  # может быть None, если не задан
                return None
        except Exception as e:
            print(f"❌ Ошибка при получении payment_message_id: {e}")
            raise

    def check_order_code_unique(self, order_code: int) -> bool:
        """
        Проверяет, существует ли order_code в таблице orders.
        :param order_code: Номер заказа, который нужно проверить
        :return: True, если код уникален, иначе False
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT COUNT(*)
                    FROM orders
                    WHERE order_code = %s
                """
                cursor.execute(query, (order_code,))
                count = cursor.fetchone()[0]
                return count == 0  # True, если код не найден
        except Exception as e:
            print(f"Error checking order code uniqueness: {e}")
            return False  # В случае ошибки считаем код не уникальным

    def get_order_by_code(self, order_code: int):
        """
        Получение информации о заказе по order_id.
        :param order_code: Уникальный код заказа.
        :return: Словарь с данными заказа или None.
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM orders WHERE order_code = %s
                """, (order_code,))
                return cursor.fetchone()
        except Exception as e:
            self.conn.rollback()
            print(f"Error getting order: {e}")
            return None

    def get_order_by_id(self, order_id: int):
        """
        Получение информации о заказе по order_id.
        :param order_id: ID заказа.
        :return: Словарь с данными заказа или None.
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT * FROM orders WHERE order_id = %s
                """, (order_id,))
                return cursor.fetchone()
        except Exception as e:
            self.conn.rollback()
            print(f"Error getting order by id: {e}")
            return None

    def grant_manual_access(self, user_id: int, granted_by: int):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO manual_access (user_id, course_chapter, granted_by)
                    VALUES (%s, 'course', %s)
                    ON CONFLICT (user_id, course_chapter) DO NOTHING
                """, (user_id, granted_by))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при добавлении доступа в manual_access: {e}")
            self.conn.rollback()
            raise

    def has_manual_access(self, user_id: int, course_chapter: str) -> bool:
        """
        Проверяет, был ли пользователю вручную выдан доступ к курсу.

        :param user_id: Telegram ID пользователя.
        :param course_chapter: Игнорируется, у нас только один курс.
        :return: True, если доступ есть, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM manual_access
                        WHERE user_id = %s AND course_chapter = 'course'
                    )
                """, (user_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"❌ Ошибка при проверке ручного доступа: {e}")
            return False

    # ===== ФУНКЦИИ ДЛЯ ПОДПИСОК =====

    def create_subscription(self, user_id: int, order_id: int) -> int:
        """
        Создает новую подписку.
        
        :param user_id: Telegram user ID
        :param order_id: ID заказа
        :return: subscription_id
        """
        try:
            with self.conn.cursor() as cursor:
                # Вычисляем дату следующего платежа (то же число следующего месяца)
                now = datetime.now()
                if now.month == 12:
                    # Если декабрь, то следующий месяц - январь следующего года
                    next_payment_date = now.replace(year=now.year + 1, month=1)
                else:
                    # Иначе просто увеличиваем месяц
                    next_payment_date = now.replace(month=now.month + 1)
                
                # Устанавливаем даты: начало сейчас, конец через месяц
                query = """
                    INSERT INTO subscriptions (user_id, order_id, start_date, end_date, next_payment_date)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + INTERVAL '1 month', %s)
                    RETURNING subscription_id;
                """
                cursor.execute(query, (user_id, order_id, next_payment_date))
                subscription_id = cursor.fetchone()[0]
                self.conn.commit()
                return subscription_id
        except Exception as e:
            print(f"❌ Ошибка при создании подписки: {e}")
            self.conn.rollback()
            raise

    def get_active_subscription(self, user_id: int):
        """
        Получает активную подписку пользователя.
        
        :param user_id: Telegram user ID
        :return: Словарь с данными подписки или None
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT * FROM subscriptions 
                    WHERE user_id = %s AND status = 'active' AND end_date > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                cursor.execute(query, (user_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"❌ Ошибка при получении активной подписки: {e}")
            return None

    def update_subscription_status(self, subscription_id: int, status: str):
        """
        Обновляет статус подписки.
        
        :param subscription_id: ID подписки
        :param status: Новый статус
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    UPDATE subscriptions 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE subscription_id = %s
                """
                cursor.execute(query, (status, subscription_id))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении статуса подписки: {e}")
            self.conn.rollback()
            raise

    def extend_subscription(self, subscription_id: int):
        """
        Продлевает подписку на месяц.
        
        :param subscription_id: ID подписки
        """
        try:
            with self.conn.cursor() as cursor:
                # Получаем текущую дату следующего платежа
                cursor.execute("""
                    SELECT next_payment_date FROM subscriptions WHERE subscription_id = %s
                """, (subscription_id,))
                current_next_payment = cursor.fetchone()[0]
                
                # Вычисляем новую дату (то же число следующего месяца)
                if current_next_payment.month == 12:
                    # Если декабрь, то следующий месяц - январь следующего года
                    new_next_payment = current_next_payment.replace(year=current_next_payment.year + 1, month=1)
                else:
                    # Иначе просто увеличиваем месяц
                    new_next_payment = current_next_payment.replace(month=current_next_payment.month + 1)
                
                # Обновляем подписку
                query = """
                    UPDATE subscriptions 
                    SET end_date = end_date + INTERVAL '1 month',
                        next_payment_date = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE subscription_id = %s
                """
                cursor.execute(query, (new_next_payment, subscription_id))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при продлении подписки: {e}")
            self.conn.rollback()
            raise

    def has_active_subscription(self, user_id: int) -> bool:
        """
        Проверяет, есть ли у пользователя активная подписка.
        
        :param user_id: Telegram user ID
        :return: True, если есть активная подписка
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT EXISTS (
                        SELECT 1 FROM subscriptions 
                        WHERE user_id = %s AND status = 'active' AND end_date > CURRENT_TIMESTAMP
                    )
                """
                cursor.execute(query, (user_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"❌ Ошибка при проверке активной подписки: {e}")
            return False

    def get_subscription_by_id(self, subscription_id: int):
        """
        Получает подписку по ID.
        
        :param subscription_id: ID подписки
        :return: Словарь с данными подписки или None
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT * FROM subscriptions 
                    WHERE subscription_id = %s
                """
                cursor.execute(query, (subscription_id,))
                return cursor.fetchone()
        except Exception as e:
            print(f"❌ Ошибка при получении подписки: {e}")
            return None

    def get_all_active_subscriptions(self):
        """
        Получает все активные подписки.
        
        :return: Список активных подписок
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT * FROM subscriptions 
                    WHERE status = 'active' AND end_date > CURRENT_TIMESTAMP
                    ORDER BY next_payment_date ASC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            print(f"❌ Ошибка при получении активных подписок: {e}")
            return []



    def schedule_job(self, user_id: int, subscription_id: int, job_type: str, run_at: datetime) -> int:
        """
        Создает задачу в scheduled_jobs для резерва.
        
        :param user_id: Telegram user ID
        :param subscription_id: ID подписки
        :param job_type: Тип задачи ('charge', 'kick', 'notify')
        :param run_at: Время выполнения
        :return: job_id
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    INSERT INTO scheduled_jobs (user_id, subscription_id, job_type, run_at)
                    VALUES (%s, %s, %s, %s)
                    RETURNING job_id;
                """
                cursor.execute(query, (user_id, subscription_id, job_type, run_at))
                job_id = cursor.fetchone()[0]
                self.conn.commit()
                return job_id
        except Exception as e:
            print(f"❌ Ошибка при создании задачи в БД: {e}")
            self.conn.rollback()
            raise

    def mark_job_done(self, job_id: int):
        """
        Отмечает задачу как выполненную.
        
        :param job_id: ID задачи
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    UPDATE scheduled_jobs 
                    SET status = 'done', updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = %s
                """
                cursor.execute(query, (job_id,))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при отметке задачи как выполненной: {e}")
            self.conn.rollback()
            raise

    def cancel_job(self, job_id: int):
        """
        Отменяет задачу.
        
        :param job_id: ID задачи
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    UPDATE scheduled_jobs 
                    SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = %s
                """
                cursor.execute(query, (job_id,))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при отмене задачи: {e}")
            self.conn.rollback()
            raise

    def update_order_email(self, order_id: int, email: str):
        """
        Обновляет email в заказе.
        
        :param order_id: ID заказа
        :param email: Email адрес
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    UPDATE orders 
                    SET email = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE order_id = %s
                """
                cursor.execute(query, (email, order_id))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при обновлении email заказа: {e}")
            self.conn.rollback()
            raise

    def cancel_subscription(self, subscription_id: int):
        """
        Отменяет подписку.
        
        :param subscription_id: ID подписки
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    UPDATE subscriptions 
                    SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE subscription_id = %s
                """
                cursor.execute(query, (subscription_id,))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при отмене подписки: {e}")
            self.conn.rollback()
            raise