FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости сначала (для лучшего кэширования слоев)
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь исходный код
COPY . .

RUN python generate.py

# Открываем порт
EXPOSE 8000

# Запускаем приложение через uvicorn
# --host 0.0.0.0 делает сервер доступным извне контейнера
# --reload включил пока тестирую для разработки (потом лучше убрать)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]