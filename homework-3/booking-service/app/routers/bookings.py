from typing import List
import uuid
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, Column, String, Integer, Numeric, DateTime, UUID as PG_UUID
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
from app.grpc_client import get_flight_grpc, reserve_seats_grpc, release_reservation_grpc
from app.interceptors import CircuitBreakerOpenError
from app.schemas import BookingCreate, BookingResponse
from app import flight_pb2
from datetime import datetime
import grpc

# SQLAlchemy setup
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Booking(Base):
    __tablename__ = "bookings"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(PG_UUID(as_uuid=True), nullable=False)
    flight_id = Column(PG_UUID(as_uuid=True), nullable=False)
    passenger_name = Column(String, nullable=False)
    passenger_email = Column(String, nullable=False)
    seat_count = Column(Integer, nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String, nullable=False, default="CONFIRMED")
    created_at = Column(DateTime, default=datetime.utcnow)

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse, status_code=201)
def create_booking(booking: BookingCreate):
    # Шаг 1: Получить информацию о рейсе
    try:
        flight_response = get_flight_grpc(booking.flight_id)
        flight = flight_response.flight
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=503, detail="Flight service is temporarily unavailable (Circuit Breaker OPEN)")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=500, detail=f"gRPC error: {e}")
    
    # Шаг 2: Зарезервировать места
    booking_id = str(uuid.uuid4())
    try:
        reserve_response = reserve_seats_grpc(
            booking.flight_id,
            booking.seat_count,
            booking_id
        )
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=503, detail="Flight service is temporarily unavailable (Circuit Breaker OPEN)")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise HTTPException(status_code=400, detail="Not enough seats")
        raise HTTPException(status_code=500, detail=f"Reservation failed: {e}")
    
    # Шаг 3: Зафиксировать цену и создать бронирование в локальной БД
    total_price = booking.seat_count * float(flight.price)
    
    db = SessionLocal()
    try:
        new_booking = Booking(
            id=uuid.UUID(booking_id),
            user_id=uuid.UUID(booking.user_id),
            flight_id=uuid.UUID(booking.flight_id),
            passenger_name=booking.passenger_name,
            passenger_email=booking.passenger_email,
            seat_count=booking.seat_count,
            total_price=total_price,
            status="CONFIRMED"
        )
        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)
        
        return {
            "id": str(new_booking.id),
            "user_id": str(new_booking.user_id),
            "flight_id": str(new_booking.flight_id),
            "passenger_name": new_booking.passenger_name,
            "passenger_email": new_booking.passenger_email,
            "seat_count": new_booking.seat_count,
            "total_price": float(new_booking.total_price),
            "status": new_booking.status,
            "created_at": new_booking.created_at.isoformat()
        }
    except Exception as e:
        db.rollback()
        try:
            release_reservation_grpc(booking_id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to create booking: {e}")
    finally:
        db.close()


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: str):
    db = SessionLocal()
    try:
        try:
            booking_uuid = uuid.UUID(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
            
        booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        return {
            "id": str(booking.id),
            "user_id": str(booking.user_id),
            "flight_id": str(booking.flight_id),
            "passenger_name": booking.passenger_name,
            "passenger_email": booking.passenger_email,
            "seat_count": booking.seat_count,
            "total_price": float(booking.total_price),
            "status": booking.status,
            "created_at": booking.created_at.isoformat()
        }
    finally:
        db.close()


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
def cancel_booking(booking_id: str):
    db = SessionLocal()
    try:
        try:
            booking_uuid = uuid.UUID(booking_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid booking ID format")
            
        booking = db.query(Booking).filter(Booking.id == booking_uuid).first()
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking.status != "CONFIRMED":
            raise HTTPException(status_code=400, detail="Booking is not confirmed")
        
        try:
            release_reservation_grpc(booking_id)
        except CircuitBreakerOpenError:
            raise HTTPException(status_code=503, detail="Flight service is temporarily unavailable (Circuit Breaker OPEN)")
        except grpc.RpcError as e:
            raise HTTPException(status_code=500, detail=f"Failed to release seats: {e}")
        
        booking.status = "CANCELLED"
        db.commit()
        db.refresh(booking)
        
        return {
            "id": str(booking.id),
            "user_id": str(booking.user_id),
            "flight_id": str(booking.flight_id),
            "passenger_name": booking.passenger_name,
            "passenger_email": booking.passenger_email,
            "seat_count": booking.seat_count,
            "total_price": float(booking.total_price),
            "status": booking.status,
            "created_at": booking.created_at.isoformat()
        }
    finally:
        db.close()


@router.get("", response_model=List[BookingResponse])
def list_bookings(user_id: uuid.UUID = Query(...)):
    db = SessionLocal()
    try:
        bookings = db.query(Booking).filter(Booking.user_id == user_id).all()
        return [
            {
                "id": str(b.id),
                "user_id": str(b.user_id),
                "flight_id": str(b.flight_id),
                "passenger_name": b.passenger_name,
                "passenger_email": b.passenger_email,
                "seat_count": b.seat_count,
                "total_price": float(b.total_price),
                "status": b.status,
                "created_at": b.created_at.isoformat()
            }
            for b in bookings
        ]
    finally:
        db.close()