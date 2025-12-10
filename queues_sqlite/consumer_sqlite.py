import socket
import sqlite3
import time
from pathlib import Path
from typing import Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "queue.db"

WORK_DURATION_SECONDS = 30   # symulacja czasu "rozmowy"
POLL_INTERVAL_SECONDS = 5    # co ile sekund sprawdzamy kolejkę


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_FILE), timeout=5.0)
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


def claim_pending_job() -> Optional[Tuple[str, str]]:
    """
    Próbuje "przejąć" jedno zadanie ze statusem 'pending'.
    Działa w transakcji, żeby przy wielu konsumentach ograniczyć wyścigi.
    Zwraca (job_id, description) albo None, jeśli brak pending.
    """
    conn = get_connection()
    try:
        # Ręczne sterowanie transakcją
        conn.isolation_level = None  # autocommit off, będziemy używać BEGIN / COMMIT
        cur = conn.cursor()

        # Blokujemy bazę w trybie IMMEDIATE (pisanie, ale nie exclusive)
        cur.execute("BEGIN IMMEDIATE")

        # Szukamy najstarszego zadania pending
        cur.execute(
            """
            SELECT job_id, description
            FROM jobs
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT 1
            """
        )
        row = cur.fetchone()

        if row is None:
            # Brak pending - kończymy transakcję
            cur.execute("COMMIT")
            return None

        job_id = row["job_id"]
        description = row["description"]

        # Aktualizujemy status na in_progress TYLKO dla tego job_id i statusu pending
        cur.execute(
            """
            UPDATE jobs
            SET status = 'in_progress'
            WHERE job_id = ? AND status = 'pending'
            """,
            (job_id,),
        )

        if cur.rowcount == 0:
            # Ktoś inny w międzyczasie przejął to zadanie
            cur.execute("COMMIT")
            return None

        cur.execute("COMMIT")
        return job_id, description

    except sqlite3.Error as exc:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        print(f"[CONSUMER_SQLITE] Błąd podczas claim_pending_job: {exc}")
        return None
    finally:
        conn.close()


def mark_job_done(job_id: str) -> None:
    """
    Ustawia status zadania na 'done'.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'done'
            WHERE job_id = ?
            """,
            (job_id,),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    init_db()
    worker_name = socket.gethostname()
    print(f"[CONSUMER_SQLITE {worker_name}] Startuję, oczekuję na zadania w SQLite...")

    while True:
        claimed = claim_pending_job()
        if claimed is None:
            print(f"[CONSUMER_SQLITE {worker_name}] Brak zadań 'pending'. Czekam {POLL_INTERVAL_SECONDS}s...")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        job_id, description = claimed
        print(
            f"[CONSUMER_SQLITE {worker_name}] Przejąłem zadanie {job_id}: "
            f"{description} – wykonuję przez {WORK_DURATION_SECONDS}s..."
        )

        # Symulacja wykonywania "rozmowy"
        time.sleep(WORK_DURATION_SECONDS)

        mark_job_done(job_id)
        print(f"[CONSUMER_SQLITE {worker_name}] Zadanie {job_id} zakończone. Status ustawiony na 'done'.")


if __name__ == "__main__":
    main()
