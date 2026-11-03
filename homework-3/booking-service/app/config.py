import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DB_USER = os.getenv("BOOKING_DB_USER", "booking_user")
    DB_PASSWORD = os.getenv("BOOKING_DB_PASSWORD", "booking_secret")
    DB_HOST = os.getenv("BOOKING_DB_HOST", "postgres-booking")
    DB_PORT = "5432"
    DB_NAME = os.getenv("BOOKING_DB_NAME", "booking_db")
    
    FLIGHT_SERVICE_HOST = os.getenv("FLIGHT_SERVICE_HOST", "flight-service")
    FLIGHT_SERVICE_PORT = int(os.getenv("FLIGHT_SERVICE_GRPC_PORT", "50051"))

    GRPC_AUTH_KEY = os.getenv("GRPC_AUTH_KEY", "super-secret-api-key-for-homework")

    CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "3"))
    CB_RECOVERY_TIMEOUT = int(os.getenv("CB_RECOVERY_TIMEOUT", "10"))
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()