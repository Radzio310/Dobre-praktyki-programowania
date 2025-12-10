# worker_image_consumer.py
import json
import os
from typing import Any, Dict, Optional

import pika
import requests
from dotenv import load_dotenv

from api.image_api.image_detection import count_people_from_url  # patrz punkt 2

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
API_URL = os.getenv("API_URL", "http://localhost:8000")
QUEUE_NAME = "image_analyze_queue"


def send_result_to_api(
    job_id: str,
    status: str,
    people_count: Optional[int] = None,
    error: Optional[str] = None,
):
    """
    Wysyła wynik analizy do API (na endpoint internal/analyze_result).
    """
    payload = {
        "job_id": job_id,
        "status": status,
        "people_count": people_count,
        "error": error,
    }
    try:
        requests.post(f"{API_URL}/internal/analyze_result", json=payload, timeout=10)
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Nie udało się odesłać wyniku do API dla job_id={job_id}: {exc}")


def process_message(ch, method, properties, body: bytes):  # noqa: ANN001
    try:
        job: Dict[str, Any] = json.loads(body.decode("utf-8"))
        job_id = job["job_id"]
        image_url = job["image_url"]
        print(f"[x] Odebrano zadanie {job_id} dla URL: {image_url}")

        send_result_to_api(job_id, status="processing")

        people_count = count_people_from_url(image_url)
        print(f"[x] Zadanie {job_id}: wykryto {people_count} osób")

        send_result_to_api(job_id, status="done", people_count=people_count)

    except Exception as exc:  # noqa: BLE001
        print(f"[!] Błąd podczas przetwarzania zadania: {exc}")
        # Jeżeli coś poszło nie tak – raportujemy błąd.
        try:
            job = json.loads(body.decode("utf-8"))
            job_id = job.get("job_id", "unknown")
        except Exception:  # noqa: BLE001
            job_id = "unknown"

        send_result_to_api(job_id, status="error", error=str(exc))

    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=process_message)

    print(" [*] Worker oczekuje na zadania. Aby zakończyć, naciśnij CTRL+C")
    channel.start_consuming()


if __name__ == "__main__":
    main()
