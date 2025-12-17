from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import pika
from dotenv import load_dotenv

from image_detection import count_people_from_url

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
ANALYZE_QUEUE = os.getenv("ANALYZE_QUEUE", "image_analyze_queue")
RESULTS_QUEUE = os.getenv("RESULTS_QUEUE", "image_results_queue")


def _publish_result(channel: pika.adapters.blocking_connection.BlockingChannel, msg: Dict[str, Any]) -> None:
    channel.queue_declare(queue=RESULTS_QUEUE, durable=True)
    channel.basic_publish(
        exchange="",
        routing_key=RESULTS_QUEUE,
        body=json.dumps(msg).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),  # persistent
    )


def process_message(ch, method, properties, body: bytes):  # noqa: ANN001
    """
    Konsumer analizy:
    - pobiera job z ANALYZE_QUEUE (manual ack)
    - liczy osoby
    - publikuje wynik na RESULTS_QUEUE
    - ack dopiero gdy publikacja wyniku się uda
    """
    try:
        job: Dict[str, Any] = json.loads(body.decode("utf-8"))
        job_id = job["job_id"]
        image_url = job["image_url"]

        print(f"[ANALYZE] job_id={job_id} url={image_url}")

        try:
            people_count = count_people_from_url(image_url)
            result = {
                "job_id": job_id,
                "image_url": image_url,
                "status": "done",
                "people_count": people_count,
                "error": None,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": 0,
            }
        except Exception as exc:  # noqa: BLE001
            result = {
                "job_id": job_id,
                "image_url": image_url,
                "status": "error",
                "people_count": None,
                "error": str(exc),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "retry_count": 0,
            }

        _publish_result(ch, result)

        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"[ANALYZE] ack job_id={job_id}")

    except Exception as exc:  # noqa: BLE001
        print(f"[ANALYZE] ERROR: {exc} -> nack requeue")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()

    channel.queue_declare(queue=ANALYZE_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(queue=ANALYZE_QUEUE, on_message_callback=process_message, auto_ack=False)
    print(" [*] analyze-worker waiting for jobs. CTRL+C to exit.")
    channel.start_consuming()


if __name__ == "__main__":
    main()
