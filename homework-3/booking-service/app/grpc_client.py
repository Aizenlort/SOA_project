import grpc
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from app import flight_pb2
from app import flight_pb2_grpc
from app.config import settings
from app.interceptors import CircuitBreakerInterceptor, is_retryable_exception, CircuitBreakerOpenError

_channel = None
_stub = None
_cb_interceptor = None

def get_grpc_channel():
    global _channel, _cb_interceptor
    if _channel is None:
        target = f"{settings.FLIGHT_SERVICE_HOST}:{settings.FLIGHT_SERVICE_PORT}"
        _cb_interceptor = CircuitBreakerInterceptor(
            failure_threshold=settings.CB_FAILURE_THRESHOLD,
            recovery_timeout=settings.CB_RECOVERY_TIMEOUT
        )
        base_channel = grpc.insecure_channel(target)
        _channel = grpc.intercept_channel(base_channel, _cb_interceptor)
    return _channel

def get_flight_stub():
    global _stub
    if _stub is None:
        _stub = flight_pb2_grpc.FlightServiceStub(get_grpc_channel())
    return _stub

def get_metadata():
    return [('x-api-key', settings.GRPC_AUTH_KEY)]


# === Обёртки с retry для каждого gRPC-метода ===

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(is_retryable_exception),
    reraise=True
)
def search_flights_grpc(origin: str, destination: str, date: str = None):
    stub = get_flight_stub()
    return stub.SearchFlights(
        flight_pb2.SearchFlightsRequest(origin=origin, destination=destination, date=date),
        metadata=get_metadata()
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(is_retryable_exception),
    reraise=True
)
def get_flight_grpc(flight_id: str):
    stub = get_flight_stub()
    return stub.GetFlight(
        flight_pb2.GetFlightRequest(flight_id=flight_id),
        metadata=get_metadata()
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(is_retryable_exception),
    reraise=True
)
def reserve_seats_grpc(flight_id: str, seat_count: int, booking_id: str):
    stub = get_flight_stub()
    return stub.ReserveSeats(
        flight_pb2.ReserveSeatsRequest(
            flight_id=flight_id,
            seat_count=seat_count,
            booking_id=booking_id
        ),
        metadata=get_metadata()
    )

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(is_retryable_exception),
    reraise=True
)
def release_reservation_grpc(booking_id: str):
    stub = get_flight_stub()
    return stub.ReleaseReservation(
        flight_pb2.ReleaseReservationRequest(booking_id=booking_id),
        metadata=get_metadata()
    )