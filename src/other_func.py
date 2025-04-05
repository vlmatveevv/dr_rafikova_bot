import random
import string
import html
from setup import pdb


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