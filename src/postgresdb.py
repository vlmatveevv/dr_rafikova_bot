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

    def add_payment(self, payment_id: str, amount: float, income_amount: float,
                    payment_method_type: str, user_id: int, status: str,
                    order_id: int) -> bool:
        """
        Добавляет новый платеж в таблицу payments.

        :param payment_id: Уникальный идентификатор платежа (VARCHAR).
        :param amount: Сумма платежа (NUMERIC(8,2)).
        :param income_amount: Сумма, фактически поступившая на счет (NUMERIC(8,2)).
        :param payment_method_type: Тип платежного метода (например, 'card', 'cash').
        :param user_id: ID пользователя.
        :param status: Статус платежа (например, 'pending', 'completed').
        :param order_id: ID заказа.
        :return: True, если платеж успешно добавлен, иначе False.
        """
        try:
            with self.conn.cursor() as cursor:
                query = """
                    INSERT INTO payments (payment_id, amount, income_amount, 
                                          payment_method_type, user_id, status, 
                                          created_at, updated_at, order_id)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), %s)
                """
                params = (payment_id, amount, income_amount, payment_method_type,
                          user_id, status, order_id)
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

    def payment_exists(self, payment_id: str) -> bool:
        """
        Проверка, существует ли платеж с данным payment_id в базе данных.
        :param payment_id: Уникальный ID платежа
        :return: True, если платеж существует, иначе False
        """
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT EXISTS(SELECT 1 FROM payments WHERE payment_id = %s)
                """, (payment_id,))
                return cursor.fetchone()[0]
        except Exception as e:
            self.conn.rollback()
            print(f"Error checking payment existence: {e}")
            return False