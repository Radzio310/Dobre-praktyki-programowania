from __future__ import annotations

import time
import subprocess
import requests

SERVICE_B = "http://localhost:8002"
SERVICE_A = "http://localhost:8001"

TEST_IMAGE_URL = "https://upload.wikimedia.org/wikipedia/commons/3/3f/Fronalpstock_big.jpg"


def wait_for(url: str, timeout_s: int = 30) -> None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return
            last = f"{r.status_code} {r.text}"
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
        time.sleep(1)
    raise AssertionError(f"Service not ready: {url}. Last: {last}")


def poll_result(job_id: str, timeout_s: int = 120) -> dict:
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        r = requests.get(f"{SERVICE_A}/results/{job_id}", timeout=5)
        if r.status_code == 200:
            return r.json()
        last_status = f"{r.status_code} {r.text}"
        time.sleep(2)
    raise AssertionError(f"Timeout waiting for result in Service A. Last: {last_status}")


def compose(cmd: list[str]) -> None:
    # Uruchamia "docker compose ..." w sposób przenośny
    full = ["docker", "compose", *cmd]
    p = subprocess.run(full, capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"Command failed: {' '.join(full)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")


def test_e2e_happy_path():
    wait_for(f"{SERVICE_B}/health", 30)
    wait_for(f"{SERVICE_A}/health", 30)

    r = requests.post(
        f"{SERVICE_B}/analyze_img",
        json={"image_url": TEST_IMAGE_URL},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert job_id

    data = poll_result(job_id, 180)
    assert data["job_id"] == job_id
    assert data["status"] in ("done", "error")


def test_e2e_resilience_service_a_down_then_up():
    wait_for(f"{SERVICE_B}/health", 30)
    wait_for(f"{SERVICE_A}/health", 30)

    # Stop A (symulacja przestoju/Cloudflare)
    compose(["stop", "service-a"])

    r = requests.post(
        f"{SERVICE_B}/analyze_img",
        json={"image_url": TEST_IMAGE_URL},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert job_id

    # Włącz A ponownie
    compose(["start", "service-a"])
    wait_for(f"{SERVICE_A}/health", 30)

    data = poll_result(job_id, 240)
    assert data["job_id"] == job_id
    assert data["status"] in ("done", "error")
