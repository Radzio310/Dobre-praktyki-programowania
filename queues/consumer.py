import csv
import os
import socket
import time
from typing import Dict, List, Optional

QUEUE_FILE = "jobs.csv"
WORK_DURATION_SECONDS = 30   # wykonywanie jednej "rozmowy"
POLL_INTERVAL_SECONDS = 5    # co ile sekund sprawdzamy kolejkę


def load_jobs() -> List[Dict[str, str]]:
    """
    Wczytuje wszystkie zadania z pliku kolejki jako listę dictów.
    Jeśli pliku nie ma, zwraca pustą listę.
    """
    if not os.path.exists(QUEUE_FILE):
        return []

    jobs: List[Dict[str, str]] = []
    with open(QUEUE_FILE, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            jobs.append(row)
    return jobs


def save_jobs(jobs: List[Dict[str, str]]) -> None:
    """
    Zapisuje listę zadań z powrotem do pliku CSV.
    Nadpisuje cały plik.
    """
    # Upewniamy się, że są wszystkie kolumny.
    fieldnames = ["job_id", "status", "description"]
    with open(QUEUE_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow({
                "job_id": job["job_id"],
                "status": job["status"],
                "description": job.get("description", ""),
            })


def pick_pending_job(jobs: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """
    Zwraca pierwsze zadanie ze statusem 'pending' lub None, jeśli takiego nie ma.
    """
    for job in jobs:
        if job.get("status") == "pending":
            return job
    return None


def main() -> None:
    worker_name = socket.gethostname()

    print(f"[CONSUMER {worker_name}] Startuję, oczekuję na zadania...")
    while True:
        jobs = load_jobs()

        job = pick_pending_job(jobs)
        if job is None:
            print(f"[CONSUMER {worker_name}] Brak zadań 'pending'. Czekam {POLL_INTERVAL_SECONDS}s...")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        job_id = job["job_id"]
        description = job["description"]
        print(f"[CONSUMER {worker_name}] Znalazłem zadanie pending: {description}")

        # KROK 1: oznaczamy zadanie jako 'in_progress' i zapisujemy plik
        for j in jobs:
            if j["job_id"] == job_id and j["status"] == "pending":
                j["status"] = "in_progress"
                break

        save_jobs(jobs)
        print(f"[CONSUMER {worker_name}] | {description} oznaczone jako in_progress. Wykonuję pracę {WORK_DURATION_SECONDS}s...")

        # Symulacja wykonywania pracy (np. rozmowy telefonicznej)
        time.sleep(WORK_DURATION_SECONDS)

        # KROK 2: po wykonaniu ponownie wczytujemy plik (ktoś mógł coś zmienić w międzyczasie)
        jobs = load_jobs()
        for j in jobs:
            if j["job_id"] == job_id:
                j["status"] = "done"
                break

        save_jobs(jobs)
        print(f"[CONSUMER {worker_name}] | {description} zakończone. Status ustawiony na 'done'.")


if __name__ == "__main__":
    main()
