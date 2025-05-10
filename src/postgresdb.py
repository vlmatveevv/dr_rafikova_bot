import json
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values
import config
import logging
from datetime import datetime

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

        :param user_id: ID пользователя.
        :return: Список названий курсов (course_chapter).
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT DISTINCT o.course_chapter
                    FROM orders o
                    JOIN payments p ON o.order_id = p.order_id
                    WHERE o.user_id = %s
                """
                cursor.execute(query, (user_id,))
                result = cursor.fetchall()
                return [row[0] for row in result]  # список course_chapter
        except Exception as e:
            print(f"Ошибка при получении курсов: {e}")
            return []

    # def get_all_user_courses(self, user_id: int) -> list:
    #     """
    #     Возвращает список всех курсов, к которым у пользователя есть доступ:
    #     - оплаченные
    #     - выданные вручную (manual_access)
    #
    #     :param user_id: Telegram user ID
    #     :return: список course_chapter
    #     """
    #     try:
    #         with self.conn.cursor() as cursor:
    #             query = """
    #                 SELECT DISTINCT course_chapter FROM (
    #                     SELECT o.course_chapter
    #                     FROM orders o
    #                     JOIN payments p ON o.order_id = p.order_id
    #                     WHERE o.user_id = %s
    #                     UNION
    #                     SELECT ma.course_chapter
    #                     FROM manual_access ma
    #                     WHERE ma.user_id = %s
    #                 ) AS combined
    #             """
    #             cursor.execute(query, (user_id, user_id))
    #             result = cursor.fetchall()
    #             return [row[0] for row in result]
    #     except Exception as e:
    #         print(f"❌ Ошибка при получении всех доступных курсов: {e}")
    #         return []

    def get_all_user_courses(self, user_id: int) -> list:
        """
        Возвращает список всех курсов, к которым у пользователя есть доступ:
        - оплаченные (в orders)
        - выданные вручную (manual_access)

        :param user_id: Telegram user ID
        :return: список course_chapter
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT DISTINCT unnest(course_chapter) AS chapter FROM (
                        SELECT o.course_chapter
                        FROM orders o
                        JOIN payments p ON o.order_id = p.order_id
                        WHERE o.user_id = %s
                        UNION ALL
                        SELECT ARRAY[ma.course_chapter]  -- manual_access.course_chapter — строка
                        FROM manual_access ma
                        WHERE ma.user_id = %s
                    ) AS combined
                """
                cursor.execute(query, (user_id, user_id))
                result = cursor.fetchall()
                return [row[0] for row in result]
        except Exception as e:
            print(f"❌ Ошибка при получении всех доступных курсов: {e}")
            return []

    # def has_paid_course(self, user_id: int, course_chapter: str) -> bool:
    #     """
    #     Проверяет, оплатил ли пользователь указанный курс.
    #
    #     :param user_id: ID пользователя.
    #     :param course_chapter: Название курса/раздела.
    #     :return: True, если оплата есть, иначе False.
    #     """
    #     try:
    #         with self.conn.cursor() as cursor:
    #             query = """
    #                 SELECT EXISTS (
    #                     SELECT 1
    #                     FROM orders o
    #                     JOIN payments p ON o.order_id = p.order_id
    #                     WHERE o.user_id = %s AND o.course_chapter = %s
    #                 )
    #             """
    #             cursor.execute(query, (user_id, course_chapter))
    #             result = cursor.fetchone()
    #             return result[0]  # True или False
    #     except Exception as e:
    #         print(f"Ошибка при проверке оплаты курса: {e}")
    #         return False

    def has_paid_course(self, user_id: int, course_chapter: str) -> bool:
        """
        Проверяет, оплатил ли пользователь указанный курс.

        :param user_id: ID пользователя.
        :param course_chapter: Название курса/раздела.
        :return: True, если оплата есть, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    SELECT EXISTS (
                        SELECT 1
                        FROM orders o
                        JOIN payments p ON o.order_id = p.order_id
                        WHERE o.user_id = %s AND %s = ANY(o.course_chapter)
                    )
                """
                cursor.execute(query, (user_id, course_chapter))
                result = cursor.fetchone()
                return result[0]  # True или False
        except Exception as e:
            print(f"Ошибка при проверке оплаты курса: {e}")
            return False

    def create_order(self, user_id: int, course_chapter: str, order_code: int) -> int:
        """
        Создает заказ в таблице orders и возвращает order_id.
        Email будет добавлен позже.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    INSERT INTO orders (user_id, course_chapter, order_code)
                    VALUES (%s, %s, %s)
                    RETURNING order_id;
                """
                cursor.execute(query, (user_id, course_chapter, order_code))
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

    def grant_manual_access(self, user_id: int, course_chapter: str, granted_by: int):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO manual_access (user_id, course_chapter, granted_by)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (user_id, course_chapter) DO NOTHING
                """, (user_id, course_chapter, granted_by))
                self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при добавлении доступа в manual_access: {e}")
            self.conn.rollback()
            raise

    def has_manual_access(self, user_id: int, course_chapter: str) -> bool:
        """
        Проверяет, был ли пользователю вручную выдан доступ к курсу.

        :param user_id: Telegram ID пользователя.
        :param course_chapter: Название курса (например, 'ch_1').
        :return: True, если доступ есть, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM manual_access
                        WHERE user_id = %s AND course_chapter = %s
                    )
                """, (user_id, course_chapter))
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"❌ Ошибка при проверке ручного доступа: {e}")
            return False