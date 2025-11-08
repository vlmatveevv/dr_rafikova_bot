FROM python:3.10-slim

# Set environment variables
ENV LANG ru_RU.UTF-8
ENV LANGUAGE ru_RU:ru
ENV LC_ALL ru_RU.UTF-8
ENV ADMIN_SECRET=DISABLED
ENV LOGGING_LEVEL=debug
ENV DOCKER_MODE=true

WORKDIR /app

# Install dependencies required for psycopg2
RUN apt-get update && apt-get install -y locales procps libpq-dev gcc && \
    sed -i '/ru_RU.UTF-8/s/^# //g' /etc/locale.gen && locale-gen

# Install Python dependencies
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bundle app source
COPY src /app
COPY media /app/media
COPY config /app/config
COPY data /app/data

CMD ["python", "__main__.py"]
