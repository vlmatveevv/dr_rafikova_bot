from pathlib import Path
import yaml
import os
import dotenv

base_dir = Path(__file__).parent
config_dir = base_dir.joinpath("config")
media_dir = base_dir.joinpath("media")
data_dir = base_dir.joinpath("data")


# Функция для чтения YAML файла
def read_yaml_file(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


# Чтение конфигурационных файлов
cfg = read_yaml_file(config_dir.joinpath("config.yml"))
other_cfg = read_yaml_file(config_dir.joinpath("other.yml"))
bot_msg = read_yaml_file(config_dir.joinpath("bot_messages.yml"))
admin_msg = read_yaml_file(config_dir.joinpath("admin_messages.yml"))

bot_btn = read_yaml_file(config_dir.joinpath("bot_buttons.yml"))

config_env = dotenv.dotenv_values(config_dir / ".env")

courses = read_yaml_file(data_dir.joinpath("courses.yml"))

channel_map = {}

for key, value in courses.items():
    if isinstance(value, dict):
        channel_id = value.get('channel_id')
        channel_invite_link = value.get('channel_invite_link')
        name = value.get('name')
        if channel_id and channel_invite_link and name:
            channel_map[channel_id] = {
                'name': name,
                'channel_invite_link': channel_invite_link
            }

channel_id_to_key = {
    value["channel_id"]: key
    for key, value in courses.items()
    if isinstance(value, dict) and "channel_id" in value
}