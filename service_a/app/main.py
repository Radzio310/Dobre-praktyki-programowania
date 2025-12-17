from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .db import SessionLocal, ResultRecord, init_db


class ResultIn(BaseModel):
    job_id: str = Field(..., min_length=8, max_length=64)
    image_url: str = Field(..., min_length=8)

    status: str = Field(..., pattern="^(done|error)$")
    people_count: Optional[int] = Field(default=None, ge=0)
    error: Optional[str] = None

    processed_at: Optional[datetime] = None


class ResultOut(ResultIn):
    created_at: datetime
    updated_at: datetime


app = FastAPI(title="Service A - Results API", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/results", response_model=ResultOut)
def upsert_result(payload: ResultIn):
    """
    Idempotentny zapis wyników po job_id (retry z dispatchera nie dubluje rekordów).
    """
    with SessionLocal() as db:
        existing = db.get(ResultRecord, payload.job_id)
        if existing is None:
            rec = ResultRecord(
                job_id=payload.job_id,
                image_url=payload.image_url,
                status=payload.status,
                people_count=payload.people_count,
                error=payload.error,
                processed_at=payload.processed_at,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            return ResultOut(
                job_id=rec.job_id,
                image_url=rec.image_url,
                status=rec.status,
                people_count=rec.people_count,
                error=rec.error,
                processed_at=rec.processed_at,
                created_at=rec.created_at,
                updated_at=rec.updated_at,
            )

        # Upsert (idempotentny) – nadpisujemy stan, bo retry może wysyłać to samo.
        existing.image_url = payload.image_url
        existing.status = payload.status
        existing.people_count = payload.people_count
        existing.error = payload.error
        existing.processed_at = payload.processed_at
        db.commit()
        db.refresh(existing)

        return ResultOut(
            job_id=existing.job_id,
            image_url=existing.image_url,
            status=existing.status,
            people_count=existing.people_count,
            error=existing.error,
            processed_at=existing.processed_at,
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )


@app.get("/results/{job_id}", response_model=ResultOut)
def get_result(job_id: str):
    with SessionLocal() as db:
        rec = db.get(ResultRecord, job_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="Result not found")

        return ResultOut(
            job_id=rec.job_id,
            image_url=rec.image_url,
            status=rec.status,
            people_count=rec.people_count,
            error=rec.error,
            processed_at=rec.processed_at,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )
