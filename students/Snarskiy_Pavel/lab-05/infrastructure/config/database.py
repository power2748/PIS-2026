from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from infrastructure.db.models import Base
import os
 
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://restaurant:secret@localhost:5432/restaurant_db"
)
 
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,     # проверка соединения перед выдачей из пула
    echo=False,
)
 
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
 
 
def get_db() -> Session:
    """Dependency для FastAPI: выдаёт сессию и закрывает после запроса"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()