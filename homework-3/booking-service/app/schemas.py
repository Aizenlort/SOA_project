from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FlightStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class BookingStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"

class FlightResponse(BaseModel):
    id: str
    flight_number: str
    departure_airport: str
    arrival_airport: str
    departure_time: str
    arrival_time: str
    total_seats: int
    available_seats: int
    price: float
    status: str

class BookingCreate(BaseModel):
    user_id: str
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_count: int

class BookingResponse(BaseModel):
    id: str
    user_id: str
    flight_id: str
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: float
    status: str
    created_at: str