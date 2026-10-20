import time
import json
import uuid
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.security import decode_token

# Настройка JSON-логгера
logger = logging.getLogger("api_logger")
logger.setLevel(logging.INFO)

# Создаём handler, который пишет в stdout (в docker-compose logs)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


def mask_passwords(data: dict) -> dict:
    """Маскирует пароли в request body"""
    masked = data.copy()
    for key in masked:
        if "password" in key.lower():
            masked[key] = "***"
    return masked


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Генерируем или берём request_id
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        
        # 2. Засекаем время
        start_time = time.time()
        
        # 3. Читаем body (для мутирующих запросов)
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body = json.loads(body_bytes)
                    body = mask_passwords(body)
            except Exception:
                body = "<unable to parse>"
        
        # 4. Пытаемся извлечь user_id из токена
        user_id = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = decode_token(token, token_type="access")
                user_id = payload.get("sub")
            except Exception:
                user_id = None
        
        # 5. Обрабатываем запрос
        response = await call_next(request)
        
        # 6. Считаем длительность
        duration_ms = round((time.time() - start_time) * 1000, 2)
        
        # 7. Формируем лог-запись
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "request_id": request_id,
            "method": request.method,
            "endpoint": str(request.url.path),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
        }
        
        # Добавляем body для мутирующих запросов
        if body is not None:
            log_entry["request_body"] = body
        
        # 8. Выводим лог в JSON формате
        logger.info(json.dumps(log_entry, ensure_ascii=False))
        
        # 9. Пробрасываем request_id в ответ
        response.headers["X-Request-Id"] = request_id
        
        return response