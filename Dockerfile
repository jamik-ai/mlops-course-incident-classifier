# Dockerfile
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY src/ ./src/
COPY models/ ./models/

# Устанавливаем PYTHONPATH
ENV PYTHONPATH=/app

# Открываем порт
EXPOSE 8000

# Команда для запуска
CMD ["uvicorn", "src.api.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]