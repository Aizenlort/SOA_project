import grpc
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.grpc_client import search_flights_grpc, get_flight_grpc
from app.interceptors import CircuitBreakerOpenError
from app.schemas import FlightResponse
from app import flight_pb2
from datetime import datetime

router = APIRouter(prefix="/flights", tags=["flights"])


@router.get("", response_model=List[FlightResponse])
def search_flights(
    origin: str = Query(..., description="IATA код аэропорта вылета"),
    destination: str = Query(..., description="IATA код аэропорта прилёта"),
    date: Optional[str] = Query(None, description="Дата вылета в формате YYYY-MM-DD")
):
    try:
        response = search_flights_grpc(origin.upper(), destination.upper(), date)
        
        flights = []
        for f in response.flights:
            flights.append({
                "id": f.id,
                "flight_number": f.flight_number,
                "departure_airport": f.departure_airport,
                "arrival_airport": f.arrival_airport,
                "departure_time": f.departure_time.ToDatetime().isoformat(),
                "arrival_time": f.arrival_time.ToDatetime().isoformat(),
                "total_seats": f.total_seats,
                "available_seats": f.available_seats,
                "price": f.price,
                "status": flight_pb2.FlightStatus.Name(f.status).replace("FLIGHT_STATUS_", "")
            })
        return flights
        
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=503, detail="Flight service is temporarily unavailable (Circuit Breaker OPEN)")
    except grpc.RpcError as e:
        raise HTTPException(status_code=500, detail=f"gRPC error: {e}")


@router.get("/{flight_id}", response_model=FlightResponse)
def get_flight(flight_id: str):
    try:
        response = get_flight_grpc(flight_id)
        f = response.flight
        
        return {
            "id": f.id,
            "flight_number": f.flight_number,
            "departure_airport": f.departure_airport,
            "arrival_airport": f.arrival_airport,
            "departure_time": f.departure_time.ToDatetime().isoformat(),
            "arrival_time": f.arrival_time.ToDatetime().isoformat(),
            "total_seats": f.total_seats,
            "available_seats": f.available_seats,
            "price": f.price,
            "status": flight_pb2.FlightStatus.Name(f.status).replace("FLIGHT_STATUS_", "")
        }
        
    except CircuitBreakerOpenError:
        raise HTTPException(status_code=503, detail="Flight service is temporarily unavailable (Circuit Breaker OPEN)")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=500, detail=f"gRPC error: {e}")