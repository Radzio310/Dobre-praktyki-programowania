from __future__ import annotations

import json
import os

import pika
import pytest
from fastapi.testclient import TestClient

os.environ["RABBITMQ_URL"] = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
os.environ["ANALYZE_QUEUE"] = os.getenv("ANALYZE_QUEUE", "image_analyze_queue")

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    return TestClient(app)


def _purge_queue(queue_name: str):
    params = pika.URLParameters(os.environ["RABBITMQ_URL"])
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=queue_name, durable=True)
    ch.queue_purge(queue=queue_name)
    conn.close()


def _get_one(queue_name: str):
    params = pika.URLParameters(os.environ["RABBITMQ_URL"])
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=queue_name, durable=True)
    method, props, body = ch.basic_get(queue=queue_name, auto_ack=True)
    conn.close()
    if method is None:
        return None
    return body


@pytest.mark.integration
def test_analyze_img_enqueues_job(client: TestClient):
    queue = os.environ["ANALYZE_QUEUE"]
    _purge_queue(queue)

    r = client.post("/analyze_img", json={"image_url": "https://example.com/x.jpg"})
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert job_id

    body = _get_one(queue)
    assert body is not None, "Expected message on analyze queue"
    msg = json.loads(body.decode("utf-8"))
    assert msg["job_id"] == job_id
    assert msg["image_url"] == "https://example.com/x.jpg"
