import sys
import grpc

# Добавляем текущую папку в пути поиска модулей
sys.path.insert(0, '.')

from app import flight_pb2
from app import flight_pb2_grpc

# Подключаемся к Flight Service напрямую (через порт 50051)
channel = grpc.insecure_channel('localhost:50051')
stub = flight_pb2_grpc.FlightServiceStub(channel)

print("=" * 60)
print("ТЕСТ 1: Запрос БЕЗ API ключа (должен вернуть UNAUTHENTICATED)")
print("=" * 60)
try:
    response = stub.SearchFlights(
        flight_pb2.SearchFlightsRequest(
            origin="SVO",
            destination="LED",
            date="2026-04-01"
        )
        # metadata НЕ передаём — это и есть тест
    )
    print(f"❌ ОШИБКА: запрос прошёл без ключа! Ответ: {response}")
except grpc.RpcError as e:
    print(f"✅ Ожидаемая ошибка: {e.code()} - {e.details()}")

print()
print("=" * 60)
print("ТЕСТ 2: Запрос с НЕПРАВИЛЬНЫМ ключом (должен вернуть UNAUTHENTICATED)")
print("=" * 60)
try:
    response = stub.SearchFlights(
        flight_pb2.SearchFlightsRequest(
            origin="SVO",
            destination="LED",
            date="2026-04-01"
        ),
        metadata=[('x-api-key', 'wrong-key')]  # Неправильный ключ
    )
    print(f"❌ ОШИБКА: запрос прошёл с неправильным ключом!")
except grpc.RpcError as e:
    print(f"✅ Ожидаемая ошибка: {e.code()} - {e.details()}")

print()
print("=" * 60)
print("ТЕСТ 3: Запрос с ПРАВИЛЬНЫМ ключом (должен вернуть 200)")
print("=" * 60)
try:
    response = stub.SearchFlights(
        flight_pb2.SearchFlightsRequest(
            origin="SVO",
            destination="LED",
            date="2026-04-01"
        ),
        metadata=[('x-api-key', 'super-secret-api-key-for-homework')]  # Правильный ключ из .env
    )
    print(f"✅ Успех! Найдено рейсов: {len(response.flights)}")
    for flight in response.flights:
        print(f"   - {flight.flight_number}: {flight.departure_airport} → {flight.arrival_airport}")
except grpc.RpcError as e:
    print(f"❌ Ошибка: {e.code()} - {e.details()}")