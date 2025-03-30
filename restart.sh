# Обновить код из репозитория
git pull

# Остановить Docker-контейнеры
docker compose down

# Перезапустить Docker-контейнеры с пересборкой, указывая путь к .env файлуу
docker compose --env-file ./config/.env up -d --build