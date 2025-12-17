from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

# Ustawiamy testową bazę SQLite w pamięci procesu (oddzielnie dla testów)
os.environ["DATABASE_URL"] = "sqlite:///./test_service_a.db"

from app.main import app  # noqa: E402
from app.db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    init_db()


@pytest.fixture()
def client():
    return TestClient(app)


def test_upsert_and_get_result(client: TestClient):
    job_id = "job-12345678"
    payload = {
        "job_id": job_id,
        "image_url": "https://example.com/img.jpg",
        "status": "done",
        "people_count": 3,
        "error": None,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }

    r = client.post("/results", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["job_id"] == job_id
    assert data["status"] == "done"
    assert data["people_count"] == 3

    r2 = client.get(f"/results/{job_id}")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["job_id"] == job_id
    assert data2["people_count"] == 3


def test_idempotent_upsert(client: TestClient):
    job_id = "job-ABCDEFGH"
    payload1 = {
        "job_id": job_id,
        "image_url": "https://example.com/a.jpg",
        "status": "done",
        "people_count": 1,
        "error": None,
        "processed_at": None,
    }
    payload2 = {
        "job_id": job_id,
        "image_url": "https://example.com/a.jpg",
        "status": "done",
        "people_count": 2,  # zmiana
        "error": None,
        "processed_at": None,
    }

    r1 = client.post("/results", json=payload1)
    assert r1.status_code == 200

    r2 = client.post("/results", json=payload2)
    assert r2.status_code == 200
    assert r2.json()["people_count"] == 2

    r3 = client.get(f"/results/{job_id}")
    assert r3.status_code == 200
    assert r3.json()["people_count"] == 2
