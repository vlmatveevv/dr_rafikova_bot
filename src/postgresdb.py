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

    def add_payment(self, external_payment_id: str, amount: float, income_amount: float,
                    payment_method_type: str, order_id: int) -> bool:
        """
        Добавляет новый платеж в таблицу payments.

        :param external_payment_id: Уникальный ID платежа от платёжной системы.
        :param amount: Сумма платежа.
        :param income_amount: Сумма после вычета комиссии.
        :param payment_method_type: Тип платежного метода (например, 'card', 'sbp').
        :param order_id: ID заказа.
        :return: True, если платеж успешно добавлен, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    INSERT INTO payments (
                        external_payment_id, amount, income_amount, 
                        payment_method_type, order_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s, NOW())
                """
                params = (
                    external_payment_id,
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

    def payment_exists(self, external_payment_id: str) -> bool:
        """
        Проверка, существует ли платеж с данным payment_id в базе данных.
        :param external_payment_id: Уникальный ID платежа
        :return: True, если платеж существует, иначе False
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS(SELECT 1 FROM payments WHERE external_payment_id = %s)
                """, (external_payment_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            self.conn.rollback()
            print(f"Error checking payment existence: {e}")
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
                        WHERE o.user_id = %s AND o.course_chapter = %s
                    )
                """
                cursor.execute(query, (user_id, course_chapter))
                result = cursor.fetchone()
                return result[0]  # True или False
        except Exception as e:
            print(f"Ошибка при проверке оплаты курса: {e}")
            return False