from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from sqlalchemy import Column, String, Integer, Numeric, DateTime, Enum, UUID as PG_UUID
import uuid
import enum

class FlightStatusEnum(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

class ReservationStatusEnum(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"

class Flight(Base):
    __tablename__ = "flights"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number = Column(String(50), nullable=False)
    departure_airport = Column(String(3), nullable=False)
    arrival_airport = Column(String(3), nullable=False)
    departure_time = Column(DateTime(timezone=True), nullable=False)
    arrival_time = Column(DateTime(timezone=True), nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(FlightStatusEnum), nullable=False, default=FlightStatusEnum.SCHEDULED)

class SeatReservation(Base):
    __tablename__ = "seat_reservations"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id = Column(PG_UUID(as_uuid=True), nullable=False)
    booking_id = Column(PG_UUID(as_uuid=True), nullable=False, unique=True)
    seat_count = Column(Integer, nullable=False)
    status = Column(Enum(ReservationStatusEnum), nullable=False, default=ReservationStatusEnum.ACTIVE)