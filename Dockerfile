# Используем официальный Python образ
FROM python:3.11-slim

# Установка системных зависимостей для Canvas и шрифтов
RUN apt-get update && apt-get install -y \
    build-essential \
    libfontconfig1-dev \
    libfreetype6-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libegl1-mesa-dev \
    fonts-dejavu-core \
    fonts-dejavu-extra \
    fontconfig \
    && fc-cache -f -v \
    && rm -rf /var/lib/apt/lists/*

# Установка рабочей директории
WORKDIR /app

# Копирование requirements.txt
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание пользователя для безопасности
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

# Открытие порта
EXPOSE 3000

# Команда запуска
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "app:app"]
