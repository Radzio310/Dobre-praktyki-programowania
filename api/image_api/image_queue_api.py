# image_api/image_queue_api.py
import json
import os
from uuid import uuid4
from typing import Optional, Dict

import pika
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME = "image_analyze_queue"

router = APIRouter()

# Prosta "pseudo-baza" w pamięci:
# { job_id: {"status": "...", "people_count": int | None, "error": str | None} }
JOB_RESULTS: Dict[str, Dict[str, Optional[str]]] = {}


class AnalyzeRequest(BaseModel):
    image_url: str


class AnalyzeResult(BaseModel):
    job_id: str
    status: str
    people_count: Optional[int] = None
    error: Optional[str] = None


class InternalResultRequest(BaseModel):
    job_id: str
    status: str
    people_count: Optional[int] = None
    error: Optional[str] = None


def publish_job_to_queue(job: dict) -> None:
    """
    Wysyła zadanie na kolejkę RabbitMQ.
    """
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(job).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),  # trwała wiadomość
    )
    connection.close()


@router.post("/analyze_img", response_model=AnalyzeResult)
async def analyze_img(request: AnalyzeRequest):
    """
    Producer: NIE analizuje obrazu.
    Tworzy job_id, wrzuca zadanie na kolejkę RabbitMQ, zwraca job_id.
    """
    job_id = str(uuid4())
    job = {"job_id": job_id, "image_url": request.image_url}

    try:
        publish_job_to_queue(job)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Nie udało się wysłać zadania na kolejkę: {exc}",
        )

    JOB_RESULTS[job_id] = {"status": "queued", "people_count": None, "error": None}

    return AnalyzeResult(job_id=job_id, status="queued", people_count=None, error=None)


@router.get("/analyze_img/{job_id}", response_model=AnalyzeResult)
async def get_analyze_result(job_id: str):
    """
    Zwraca aktualny status zadania: queued / processing / done / error
    oraz liczbę osób, jeśli już policzone.
    """
    result = JOB_RESULTS.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Nie znaleziono zadania o takim job_id.")

    return AnalyzeResult(
        job_id=job_id,
        status=result["status"],
        people_count=result["people_count"],
        error=result["error"],
    )


@router.post("/internal/analyze_result")
async def internal_analyze_result(request: InternalResultRequest):
    """
    Endpoint wołany przez consumer (worker) z wynikiem analizy.
    W przyszłości dokładnie tu możesz dodać zapis do bazy. :contentReference[oaicite:2]{index=2}
    """
    JOB_RESULTS[request.job_id] = {
        "status": request.status,
        "people_count": request.people_count,
        "error": request.error,
    }
    return {"ok": True}
