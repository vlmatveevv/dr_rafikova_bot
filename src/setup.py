import pytz
import postgresdb
from datetime import datetime

pdb = postgresdb.Database()

# Установка часового пояса МСК
utc_tz = pytz.utc
moscow_tz = pytz.timezone('Europe/Moscow')


# Функция для форматирования времени в логах
def custom_time(*args):
    utc_dt = pytz.utc.localize(datetime.utcnow())
    converted = utc_dt.astimezone(moscow_tz)
    return converted.timetuple()

