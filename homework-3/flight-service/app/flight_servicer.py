import grpc
from google.protobuf import timestamp_pb2
import logging
from datetime import datetime
import uuid
from sqlalchemy import func

import flight_pb2
import flight_pb2_grpc
from database import SessionLocal, Flight, SeatReservation, FlightStatusEnum, ReservationStatusEnum
from cache import cache_get, cache_set, cache_delete, get_flight_cache_key, get_search_cache_key

logger = logging.getLogger(__name__)

class FlightServicer(flight_pb2_grpc.FlightServiceServicer):
    
    def SearchFlights(self, request, context):
        cache_key = get_search_cache_key(request.origin, request.destination, request.date or "any")
        cached = cache_get(cache_key)
        
        if cached:
            logger.info(f"CACHE HIT: {cache_key}")
            flights = []
            for f in cached:
                dep_ts = timestamp_pb2.Timestamp()
                dep_ts.FromDatetime(datetime.fromisoformat(f['departure_time']))
                
                arr_ts = timestamp_pb2.Timestamp()
                arr_ts.FromDatetime(datetime.fromisoformat(f['arrival_time']))
                
                flights.append(flight_pb2.Flight(
                    id=f['id'],
                    flight_number=f['flight_number'],
                    departure_airport=f['departure_airport'],
                    arrival_airport=f['arrival_airport'],
                    departure_time=dep_ts,
                    arrival_time=arr_ts,
                    total_seats=f['total_seats'],
                    available_seats=f['available_seats'],
                    price=f['price'],
                    status=getattr(flight_pb2.FlightStatus, f"FLIGHT_STATUS_{f['status']}")
                ))
            return flight_pb2.SearchFlightsResponse(flights=flights)

        logger.info(f"CACHE MISS: {cache_key}")
        with SessionLocal() as db:
            query = db.query(Flight).filter(
                Flight.departure_airport == request.origin.upper(),
                Flight.arrival_airport == request.destination.upper(),
                Flight.status == FlightStatusEnum.SCHEDULED
            )
            if request.date:
                query = query.filter(func.date(Flight.departure_time) == request.date)
            
            db_flights = query.all()
            
            cached_data = []
            response_flights = []
            
            for f in db_flights:
                cached_data.append({
                    "id": str(f.id),
                    "flight_number": f.flight_number,
                    "departure_airport": f.departure_airport,
                    "arrival_airport": f.arrival_airport,
                    "departure_time": f.departure_time.isoformat(),
                    "arrival_time": f.arrival_time.isoformat(),
                    "total_seats": f.total_seats,
                    "available_seats": f.available_seats,
                    "price": float(f.price),
                    "status": f.status.value
                })
                
                dep_ts = timestamp_pb2.Timestamp()
                dep_ts.FromDatetime(f.departure_time)
                arr_ts = timestamp_pb2.Timestamp()
                arr_ts.FromDatetime(f.arrival_time)
                
                response_flights.append(flight_pb2.Flight(
                    id=str(f.id),
                    flight_number=f.flight_number,
                    departure_airport=f.departure_airport,
                    arrival_airport=f.arrival_airport,
                    departure_time=dep_ts,
                    arrival_time=arr_ts,
                    total_seats=f.total_seats,
                    available_seats=f.available_seats,
                    price=float(f.price),
                    status=getattr(flight_pb2.FlightStatus, f"FLIGHT_STATUS_{f.status.value}")
                ))
            
            if cached_data:
                cache_set(cache_key, cached_data, ttl=300)
            
            return flight_pb2.SearchFlightsResponse(flights=response_flights)


    def GetFlight(self, request, context):
        cache_key = get_flight_cache_key(request.flight_id)
        cached = cache_get(cache_key)
        
        if cached:
            logger.info(f"CACHE HIT: {cache_key}")
            dep_ts = timestamp_pb2.Timestamp()
            dep_ts.FromDatetime(datetime.fromisoformat(cached['departure_time']))
            
            arr_ts = timestamp_pb2.Timestamp()
            arr_ts.FromDatetime(datetime.fromisoformat(cached['arrival_time']))
            
            flight_proto = flight_pb2.Flight(
                id=cached['id'],
                flight_number=cached['flight_number'],
                departure_airport=cached['departure_airport'],
                arrival_airport=cached['arrival_airport'],
                departure_time=dep_ts,
                arrival_time=arr_ts,
                total_seats=cached['total_seats'],
                available_seats=cached['available_seats'],
                price=cached['price'],
                status=getattr(flight_pb2.FlightStatus, f"FLIGHT_STATUS_{cached['status']}")
            )
            return flight_pb2.GetFlightResponse(flight=flight_proto)

        logger.info(f"CACHE MISS: {cache_key}")
        with SessionLocal() as db:
            flight = db.query(Flight).filter(Flight.id == request.flight_id).first()
            if not flight:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Flight not found")
                return flight_pb2.GetFlightResponse()
            
            cached_data = {
                "id": str(flight.id),
                "flight_number": flight.flight_number,
                "departure_airport": flight.departure_airport,
                "arrival_airport": flight.arrival_airport,
                "departure_time": flight.departure_time.isoformat(),
                "arrival_time": flight.arrival_time.isoformat(),
                "total_seats": flight.total_seats,
                "available_seats": flight.available_seats,
                "price": float(flight.price),
                "status": flight.status.value
            }
            cache_set(cache_key, cached_data, ttl=300)
            
            dep_ts = timestamp_pb2.Timestamp()
            dep_ts.FromDatetime(flight.departure_time)
            arr_ts = timestamp_pb2.Timestamp()
            arr_ts.FromDatetime(flight.arrival_time)
            
            return flight_pb2.GetFlightResponse(
                flight=flight_pb2.Flight(
                    id=str(flight.id),
                    flight_number=flight.flight_number,
                    departure_airport=flight.departure_airport,
                    arrival_airport=flight.arrival_airport,
                    departure_time=dep_ts,
                    arrival_time=arr_ts,
                    total_seats=flight.total_seats,
                    available_seats=flight.available_seats,
                    price=float(flight.price),
                    status=getattr(flight_pb2.FlightStatus, f"FLIGHT_STATUS_{flight.status.value}")
                )
            )


    def ReserveSeats(self, request, context):
        with SessionLocal() as db:
            existing_reservation = db.query(SeatReservation).filter(
                SeatReservation.booking_id == request.booking_id,
                SeatReservation.status == ReservationStatusEnum.ACTIVE
            ).first()
            
            if existing_reservation:
                logger.info(f"Идемпотентный вызов: резервация для {request.booking_id} уже существует")
                return flight_pb2.ReserveSeatsResponse(
                    reservation_id=str(existing_reservation.id),
                    reserved_seats=existing_reservation.seat_count,
                    total_price=0.0
                )

            flight = db.query(Flight).with_for_update().filter(Flight.id == request.flight_id).first()
            
            if not flight:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Flight not found")
                return flight_pb2.ReserveSeatsResponse()
            
            if flight.available_seats < request.seat_count:
                context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
                context.set_details("Not enough available seats")
                return flight_pb2.ReserveSeatsResponse()
            
            flight.available_seats -= request.seat_count
            
            new_reservation = SeatReservation(
                flight_id=flight.id,
                booking_id=request.booking_id,
                seat_count=request.seat_count,
                status=ReservationStatusEnum.ACTIVE
            )
            db.add(new_reservation)
            db.commit()
            
            cache_delete(get_flight_cache_key(request.flight_id))
            
            return flight_pb2.ReserveSeatsResponse(
                reservation_id=str(new_reservation.id),
                reserved_seats=new_reservation.seat_count,
                total_price=float(flight.price) * request.seat_count
            )


    def ReleaseReservation(self, request, context):
        with SessionLocal() as db:
            reservation = db.query(SeatReservation).filter(
                SeatReservation.booking_id == request.booking_id,
                SeatReservation.status == ReservationStatusEnum.ACTIVE
            ).first()
            
            if not reservation:
                return flight_pb2.ReleaseReservationResponse(success=False, message="Reservation not found or already released")
            
            flight = db.query(Flight).with_for_update().filter(Flight.id == reservation.flight_id).first()
            if flight:
                flight.available_seats += reservation.seat_count
            
            reservation.status = ReservationStatusEnum.RELEASED
            db.commit()
            
            cache_delete(get_flight_cache_key(str(reservation.flight_id)))
            
            return flight_pb2.ReleaseReservationResponse(success=True, message="Reservation released successfully")