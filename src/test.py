from jinja2 import Template
import yaml


from pathlib import Path
import yaml
import html

base_dir = Path(__file__).resolve().parent.parent  # если файл лежит в src/
admin_messages_path = base_dir / "config" / "admin_messages.yml"

with open(admin_messages_path, encoding="utf-8") as f:
    admin_msg_templates = yaml.safe_load(f)


def escape_user_data(user_info: str) -> str:
    """
    Экранирует специальные символы в пользовательских данных, такие как < и >.
    :param user_info: Строка с пользовательскими данными
    :return: Экранированная строка
    """
    return html.escape(user_info)

# Фейковые данные
user_info = {
    "user_id": 146679674,
    "first_name": ">_Romka_<",
    "last_name": "Петрова",
    "username": "alisa_preggo"
}
user_data = {
    "user_id": user_info["user_id"],
    "full_name": f"{user_info['first_name']} {user_info['last_name']}".strip(),
    "username": user_info["username"]
}

# Рендерим user_info_block
user_info_template = Template(admin_msg_templates["user_info_block"])
user_info_block = user_info_template.render(**user_data)

# Рендерим финальное сообщение
admin_template = Template(admin_msg_templates["admin_payment_notification"])
admin_payment_notification_text = admin_template.render(
    user_info_block=user_info_block,
    channel_name="2. НАЧАЛО БЕРЕМЕННОСТИ",
    out_sum=1190.0,
    payment_method_type="BankCard",
    income_amount=1190.0,
    user_id=user_info["user_id"],
    order_code=98787,
    formatted_chapter="course"
)

print(admin_payment_notification_text)