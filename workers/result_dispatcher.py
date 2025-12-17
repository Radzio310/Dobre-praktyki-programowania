from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import pika
import requests
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
RESULTS_QUEUE = os.getenv("RESULTS_QUEUE", "image_results_queue")
SERVICE_A_URL = os.getenv("SERVICE_A_URL", "http://localhost:8001").rstrip("/")

# Retry policy (sekundy) – eskalacja:
RETRY_STEPS: Tuple[int, ...] = (10, 60, 300, 1800, 3600)
MAX_RETRIES = len(RETRY_STEPS)


def utciso() -> str:
    return datetime.now(timezone.utc).isoformat()


def declare_retry_topology(ch: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """
    Topologia retry na Rabbit bez pluginów:
    - RESULTS_QUEUE: główna kolejka wyników
    - RESULTS_QUEUE.retry.<ttl>: kolejki z TTL + DLX do RESULTS_QUEUE
    - RESULTS_QUEUE.dead: dead letter po przekroczeniu limitu prób
    """
    ch.queue_declare(queue=RESULTS_QUEUE, durable=True)

    for ttl in RETRY_STEPS:
        retry_q = f"{RESULTS_QUEUE}.retry.{ttl}s"
        ch.queue_declare(
            queue=retry_q,
            durable=True,
            arguments={
                "x-message-ttl": ttl * 1000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": RESULTS_QUEUE,
            },
        )

    ch.queue_declare(queue=f"{RESULTS_QUEUE}.dead", durable=True)


def pick_retry_queue(retry_count: int) -> str:
    """
    retry_count: 0 oznacza "pierwsza porażka" -> kolejka 10s
    """
    if retry_count >= MAX_RETRIES:
        return f"{RESULTS_QUEUE}.dead"
    ttl = RETRY_STEPS[retry_count]
    return f"{RESULTS_QUEUE}.retry.{ttl}s"


def should_retry(http_status: int | None, exc: Exception | None) -> bool:
    if exc is not None:
        return True
    if http_status is None:
        return True
    # retry dla 429 i 5xx (Cloudflare / przestoje / transient)
    if http_status == 429:
        return True
    if 500 <= http_status <= 599:
        return True
    return False


def post_to_service_a(payload: Dict[str, Any]) -> Tuple[bool, int | None, str | None]:
    """
    Zwraca (ok, status_code, err).
    """
    try:
        r = requests.post(f"{SERVICE_A_URL}/results", json=payload, timeout=10)
        if 200 <= r.status_code < 300:
            return True, r.status_code, None
        return False, r.status_code, r.text
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)


def republish(ch: pika.adapters.blocking_connection.BlockingChannel, queue_name: str, msg: Dict[str, Any]) -> None:
    ch.queue_declare(queue=queue_name, durable=True)
    ch.basic_publish(
        exchange="",
        routing_key=queue_name,
        body=json.dumps(msg).encode("utf-8"),
        properties=pika.BasicProperties(delivery_mode=2),
    )


def process_message(ch, method, properties, body: bytes):  # noqa: ANN001
    """
    Konsumer wyników:
    - pobiera wynik z RESULTS_QUEUE (manual ack)
    - próbuje zapisać w Serwisie A (HTTP)
    - ack tylko przy sukcesie
    - w przypadku błędu: przerzuca na retry kolejkę (TTL/DLX) lub dead i dopiero ack
    """
    try:
        msg: Dict[str, Any] = json.loads(body.decode("utf-8"))

        retry_count = int(msg.get("retry_count", 0))
        job_id = msg.get("job_id", "unknown")
        print(f"[DISPATCH] job_id={job_id} retry_count={retry_count}")

        # payload do A (bez pól stricte transportowych)
        payload = {
            "job_id": msg["job_id"],
            "image_url": msg["image_url"],
            "status": msg["status"],
            "people_count": msg.get("people_count"),
            "error": msg.get("error"),
            "processed_at": msg.get("processed_at"),
        }

        ok, status_code, err = post_to_service_a(payload)
        if ok:
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[DISPATCH] OK job_id={job_id} ack")
            return

        # Decyzja: retry czy dead
        exc_obj = None
        retryable = should_retry(status_code, exc_obj if status_code is None else None)

        if not retryable:
            # Nie retryujemy błędów 4xx (poza 429)
            dead_msg = dict(msg)
            dead_msg["last_error"] = f"non-retryable status={status_code} err={err}"
            dead_msg["dead_at"] = utciso()

            try:
                republish(ch, f"{RESULTS_QUEUE}.dead", dead_msg)
                ch.basic_ack(delivery_tag=method.delivery_tag)
                print(f"[DISPATCH] NON-RETRY -> DEAD job_id={job_id} ack")
                return
            except Exception as pub_exc:  # noqa: BLE001
                print(f"[DISPATCH] Failed to publish to DEAD: {pub_exc} -> nack requeue")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                return

        # Retry path
        next_retry_queue = pick_retry_queue(retry_count)
        next_msg = dict(msg)
        next_msg["retry_count"] = retry_count + 1
        next_msg["last_error"] = f"status={status_code} err={err}"
        next_msg["retry_scheduled_at"] = utciso()

        try:
            republish(ch, next_retry_queue, next_msg)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f"[DISPATCH] RETRY -> {next_retry_queue} job_id={job_id} ack")
            return
        except Exception as pub_exc:  # noqa: BLE001
            print(f"[DISPATCH] Failed to publish to RETRY: {pub_exc} -> nack requeue")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            return

    except Exception as exc:  # noqa: BLE001
        print(f"[DISPATCH] ERROR parsing/processing: {exc} -> nack requeue")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


def main():
    params = pika.URLParameters(RABBITMQ_URL)

    # Prosty loop na wypadek gdyby Rabbit jeszcze wstawał
    for i in range(30):
        try:
            connection = pika.BlockingConnection(params)
            break
        except Exception:  # noqa: BLE001
            time.sleep(1)
    else:
        raise RuntimeError("Could not connect to RabbitMQ")

    channel = connection.channel()
    declare_retry_topology(channel)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RESULTS_QUEUE, on_message_callback=process_message, auto_ack=False)

    print(" [*] result-dispatcher waiting for results. CTRL+C to exit.")
    channel.start_consuming()


if __name__ == "__main__":
    main()
