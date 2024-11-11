import os
from sqlmodel import create_engine, Session
from typing import Generator

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eir_db")
engine = create_engine(DATABASE_URL, echo=True)

def get_session() -> Generator[Session, None, None]:
    """
    Create a database session generator.
    """
    with Session(engine) as session:
        yield session
