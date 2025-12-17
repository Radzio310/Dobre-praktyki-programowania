from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./service_a.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ResultRecord(Base):
    __tablename__ = "results"

    job_id = Column(String(64), primary_key=True, index=True)
    image_url = Column(Text, nullable=False)

    status = Column(String(16), nullable=False)  # done | error
    people_count = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)

    processed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
