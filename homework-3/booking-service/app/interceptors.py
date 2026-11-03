import grpc
import time
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings

logger = logging.getLogger(__name__)

# === Исключение для Circuit Breaker ===
class CircuitBreakerOpenError(Exception):
    """Вызывается, когда Circuit Breaker находится в состоянии OPEN"""
    pass

# === Circuit Breaker Interceptor ===
class CircuitBreakerInterceptor(grpc.UnaryUnaryClientInterceptor):
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 10):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = "CLOSED"
        self.failure_count = 0
        self.last_failure_time = 0.0

    def intercept_unary_unary(self, continuation, client_call_details, request):
        # Проверка состояния OPEN
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.info("Circuit Breaker: Переход в состояние HALF_OPEN")
                self.state = "HALF_OPEN"
            else:
                logger.warning("Circuit Breaker: Состояние OPEN. Возврат ошибки.")
                raise CircuitBreakerOpenError("Service unavailable due to circuit breaker")

        try:
            # Выполняем запрос
            response = continuation(client_call_details, request)
            
            if hasattr(response, 'code') and response.code() != grpc.StatusCode.OK:
                self._record_failure()
            else:
                self._record_success()
                
            return response
            
        except grpc.RpcError as e:
            self._record_failure()
            raise
        except Exception as e:
            self._record_failure()
            raise

    def _record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(f"Circuit Breaker: Зафиксирован сбой ({self.failure_count}/{self.failure_threshold})")
        
        if self.failure_count >= self.failure_threshold and self.state != "OPEN":
            logger.error("Circuit Breaker: Переход в состояние OPEN")
            self.state = "OPEN"

    def _record_success(self):
        if self.state == "HALF_OPEN":
            logger.info("Circuit Breaker: Переход в состояние CLOSED (успех в HALF_OPEN)")
            self.state = "CLOSED"
            self.failure_count = 0
        elif self.state == "CLOSED":
            self.failure_count = 0


# === Функция для Retry (используем tenacity) ===
def is_retryable_exception(e):
    """Определяет, является ли ошибка подходящей для повторной попытки"""
    if isinstance(e, grpc.RpcError):
        return e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)
    return False