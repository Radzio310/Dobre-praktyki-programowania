from __future__ import annotations

import json
import os
from typing import Any, Dict

import pika

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
ANALYZE_QUEUE = os.getenv("ANALYZE_QUEUE", "image_analyze_queue")


def publish_analyze_job(job: Dict[str, Any]) -> None:
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue=ANALYZE_QUEUE, durable=True)

    channel.basic_publish(
        exchange="",
        routing_key=ANALYZE_QUEUE,
        body=json.dumps(job).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),  # persistent
    )
    connection.close()
