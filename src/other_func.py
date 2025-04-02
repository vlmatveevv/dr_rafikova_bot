import random
import string
from setup import pdb


def generate_order_number():
    while True:
        number = ''.join(random.choices(string.digits, k=5))  # Генерируем 5 случайных цифр

        try:
            if pdb.check_order_number_unique(number):  # Проверяем уникальность
                return number
        except Exception as e:
            print(f"Error checking order number uniqueness: {e}")