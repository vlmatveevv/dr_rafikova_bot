from pathlib import Path
import yaml
import os
import dotenv

base_dir = Path(__file__).parent
config_dir = base_dir.joinpath("config")
data_dir = base_dir.joinpath("data")
media_dir = base_dir.joinpath("media")


# Функция для чтения YAML файла
def read_yaml_file(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)


# Чтение конфигурационных файлов
cfg = read_yaml_file(config_dir.joinpath("config.yml"))
other_cfg = read_yaml_file(config_dir.joinpath("other.yml"))
bot_msg = read_yaml_file(config_dir.joinpath("bot_messages.yml"))
bot_btn = read_yaml_file(config_dir.joinpath("bot_buttons.yml"))

courses = read_yaml_file(data_dir.joinpath("courses.yml"))

config_env = dotenv.dotenv_values(config_dir / ".env")
