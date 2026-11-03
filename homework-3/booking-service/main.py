from fastapi import FastAPI
from app.routers import flights, bookings

app = FastAPI(title="Booking Service", version="1.0.0")

app.include_router(flights.router)
app.include_router(bookings.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}