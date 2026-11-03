import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DB_USER = os.getenv("FLIGHT_DB_USER", "flight_user")
    DB_PASSWORD = os.getenv("FLIGHT_DB_PASSWORD", "flight_secret")
    DB_HOST = os.getenv("FLIGHT_DB_HOST", "postgres-flight")
    DB_PORT = "5432"
    DB_NAME = os.getenv("FLIGHT_DB_NAME", "flight_db")
    
    REDIS_MASTER_NAME = os.getenv("REDIS_SENTINEL_MASTER_NAME", "mymaster")
    REDIS_SENTINEL_HOST = os.getenv("REDIS_SENTINEL_HOST", "redis-sentinel")
    REDIS_SENTINEL_PORT = int(os.getenv("REDIS_SENTINEL_PORT", "26379"))

    GRPC_AUTH_KEY = os.getenv("GRPC_AUTH_KEY", "super-secret-api-key-for-homework")
    
    @property
    def database_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()