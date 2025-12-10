import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "queue.db"


def get_connection() -> sqlite3.Connection:
    """
    Zwraca połączenie do bazy SQLite.
    """
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Tworzy tabelę jobs, jeśli jeszcze nie istnieje.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def enqueue_job(description: str) -> str:
    """
    Dodaje jedno zadanie do kolejki ze statusem 'pending'.
    Zwraca job_id.
    """
    init_db()
    job_id = str(uuid4())
    created_at = datetime.now().isoformat(timespec="seconds")

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs (job_id, status, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, "pending", description, created_at),  # <-- 4 parametry
        )
        conn.commit()
    finally:
        conn.close()

    print(f"[PRODUCER_SQLITE] Dodano zadanie {job_id}: {description} ({created_at})")
    return job_id


def main() -> None:
    """
    Jedno uruchomienie produkuje 10 zadań o różnych typach.
    Opcjonalnie możesz podać prefix opisu jako argument CLI.
    """
    # Prefix opisu z argumentu CLI (opcjonalny)
    if len(sys.argv) > 1:
        prefix = " ".join(sys.argv[1:]) + " – "
    else:
        prefix = ""

    task_templates = [
        "Rozmowa telefoniczna z klientem",
        "Obsługa reklamacji dotyczącej faktury",
        "Przygotowanie oferty cenowej",
        "Wyjaśnienie różnicy w rozliczeniu usług",
        "Aktualizacja danych kontaktowych klienta",
        "Rejestracja nowego zgłoszenia serwisowego",
        "Zmiana pakietu usług na wyższy",
        "Zmiana pakietu usług na tańszy",
        "Wyjaśnienie naliczenia opłaty serwisowej",
        "Przekazanie sprawy do działu technicznego",
    ]

    print("[PRODUCER_SQLITE] Dodaję 10 nowych zadań do kolejki...")
    for i in range(10):
        template = task_templates[i % len(task_templates)]
        description = f"{prefix}{template} (batch-{datetime.now().strftime('%Y%m%d-%H%M%S')} #{i+1})"
        enqueue_job(description)

    print("[PRODUCER_SQLITE] Gotowe – 10 zadań dodanych.")


if __name__ == "__main__":
    main()
