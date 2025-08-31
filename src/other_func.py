import random
import string
import html
from setup import pdb
from datetime import datetime
import calendar


def add_one_month_safe(dt: datetime) -> datetime:
    # считаем следующий месяц/год
    if dt.month == 12:
        year, month = dt.year + 1, 1
    else:
        year, month = dt.year, dt.month + 1
    # последний день следующего месяца
    last_day = calendar.monthrange(year, month)[1]
    # если, например, было 31, а в след. месяце 30 — ставим 30
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def generate_order_number():
    while True:
        number = ''.join(random.choices(string.digits, k=5))  # Генерируем 5 случайных цифр

        try:
            if pdb.check_order_code_unique(number):  # Проверяем уникальность
                return number
        except Exception as e:
            print(f"Error checking order number uniqueness: {e}")


def escape_user_data(user_info: str) -> str:
    """
    Экранирует специальные символы в пользовательских данных, такие как < и >.
    :param user_info: Строка с пользовательскими данными
    :return: Экранированная строка
    """
    return html.escape(user_info)