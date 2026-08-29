from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
class Base(DeclarativeBase): pass
DATABASE_URL = os.getenv("AUTH_DATABASE_URL", "sqlite:///./apps/api/tourism_gap_finder.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
