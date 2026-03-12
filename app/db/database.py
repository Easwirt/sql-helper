import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import load_project_env


load_project_env()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://appuser:apppassword@localhost:5432/app_database",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables defined in models."""
    Base.metadata.create_all(bind=engine)
