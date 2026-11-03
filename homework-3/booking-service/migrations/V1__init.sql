-- Создание ENUM типа
CREATE TYPE booking_status AS ENUM ('CONFIRMED', 'CANCELLED');

-- Таблица бронирований
CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    flight_id UUID NOT NULL,
    passenger_name VARCHAR(255) NOT NULL,
    passenger_email VARCHAR(255) NOT NULL,
    seat_count INT NOT NULL,
    total_price NUMERIC(10, 2) NOT NULL,
    status booking_status NOT NULL DEFAULT 'CONFIRMED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для оптимизации поиска
CREATE INDEX idx_bookings_user ON bookings(user_id);
CREATE INDEX idx_bookings_flight ON bookings(flight_id);