import grpc
import logging

logger = logging.getLogger(__name__)

class AuthInterceptor(grpc.ServerInterceptor):
    def __init__(self, valid_api_key: str):
        self._valid_api_key = valid_api_key

    def intercept_service(self, continuation, handler_call_details):
        # Извлекаем metadata из запроса
        metadata = dict(handler_call_details.invocation_metadata)
        api_key = metadata.get('x-api-key', '')
        
        # Проверяем ключ
        if api_key != self._valid_api_key:
            logger.warning(f"UNAUTHENTICATED: попытка доступа с ключом '{api_key}'")
            
            # Возвращаем обработчик, который всегда возвращает ошибку UNAUTHENTICATED
            return grpc.unary_unary_rpc_method_handler(
                self._deny_request,
                request_deserializer=None,
                response_serializer=None
            )
        
        # Если ключ валидный — продолжаем нормальную обработку
        return continuation(handler_call_details)

    def _deny_request(self, request, context):
        context.set_code(grpc.StatusCode.UNAUTHENTICATED)
        context.set_details("Invalid or missing API key")
        return None