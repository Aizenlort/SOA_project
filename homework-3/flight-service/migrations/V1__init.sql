-- Создание ENUM типов
CREATE TYPE flight_status AS ENUM ('SCHEDULED', 'DEPARTED', 'CANCELLED', 'COMPLETED');
CREATE TYPE reservation_status AS ENUM ('ACTIVE', 'RELEASED', 'EXPIRED');

-- Таблица рейсов
CREATE TABLE flights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_number VARCHAR(50) NOT NULL,
    departure_airport CHAR(3) NOT NULL,
    arrival_airport CHAR(3) NOT NULL,
    departure_time TIMESTAMP WITH TIME ZONE NOT NULL,
    arrival_time TIMESTAMP WITH TIME ZONE NOT NULL,
    total_seats INT NOT NULL,
    available_seats INT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    status flight_status NOT NULL DEFAULT 'SCHEDULED',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Комбинация номера рейса и даты вылета уникальна
    CONSTRAINT unique_flight_schedule UNIQUE (flight_number, departure_time)
);

-- Таблица резерваций мест
CREATE TABLE seat_reservations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    flight_id UUID NOT NULL REFERENCES flights(id) ON DELETE CASCADE,
    booking_id UUID NOT NULL,
    seat_count INT NOT NULL,
    status reservation_status NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Требование: одному бронированию ровно одна резервация
    CONSTRAINT unique_booking_reservation UNIQUE (booking_id)
);

-- Индексы для оптимизации поиска
CREATE INDEX idx_flights_route_date ON flights(departure_airport, arrival_airport, departure_time);
CREATE INDEX idx_seat_reservations_flight ON seat_reservations(flight_id);
CREATE INDEX idx_seat_reservations_booking ON seat_reservations(booking_id);