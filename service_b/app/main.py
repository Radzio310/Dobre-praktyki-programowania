from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .rabbit import publish_analyze_job


class AnalyzeRequest(BaseModel):
    image_url: str = Field(..., min_length=8)


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str


app = FastAPI(title="Service B - Analyze API", version="1.0.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze_img", response_model=AnalyzeResponse)
def analyze_img(req: AnalyzeRequest):
    """
    Producer: przyjmuje URL, tworzy job_id, publikuje na RabbitMQ.
    Nie liczy ludzi synchronicznie.
    """
    job_id = str(uuid4())
    job = {
        "job_id": job_id,
        "image_url": req.image_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        publish_analyze_job(job)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to publish job: {exc}")

    return AnalyzeResponse(job_id=job_id, status="queued")
