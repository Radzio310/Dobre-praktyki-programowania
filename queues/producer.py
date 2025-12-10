import csv
import os
import sys
from datetime import datetime
from uuid import uuid4

QUEUE_FILE = "jobs.csv"


def ensure_queue_file_exists() -> None:
    """
    Jeśli plik kolejki nie istnieje, tworzy go z nagłówkiem.
    """
    if not os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["job_id", "status", "description"])


def enqueue_job(description: str) -> str:
    """
    Dodaje jedno zadanie do pliku kolejki ze statusem 'pending'.
    Zwraca job_id.
    """
    ensure_queue_file_exists()
    job_id = str(uuid4())
    full_description = f"{description} (utworzone {datetime.now().isoformat(timespec='seconds')})"
    with open(QUEUE_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([job_id, "pending", full_description])
    print(f"[PRODUCER] Dodano zadanie {job_id}: {full_description}")
    return job_id


def main() -> None:
    # Opis zadania z argumentu CLI albo domyślny
    if len(sys.argv) > 1:
        description = " ".join(sys.argv[1:])
    else:
        description = "Rozmowa telefoniczna"

    enqueue_job(description)


if __name__ == "__main__":
    main()
