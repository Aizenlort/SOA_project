import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://user:password@localhost:5432/marketplace"
)

# Создаем асинхронный движок
engine = create_async_engine(DATABASE_URL, echo=False) # echo=True можно включить для отладки SQL-запросов

# Фабрика сессий
AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Базовый класс для всех ORM-моделей
class Base(DeclarativeBase):
    pass

# Dependency для получения сессии БД в роутерах
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session