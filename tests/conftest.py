# tests/conftest.py
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# testowa baza: api/test.db (nie dotykamy produkcyjnej movies.db)
PROJ_ROOT = Path(__file__).resolve().parents[1]
TEST_DB = PROJ_ROOT / "api" / "test.db"

@pytest.fixture(scope="session", autouse=True)
def _env():
    os.environ.setdefault("JWT_SECRET", "TEST_SECRET")
    os.environ.setdefault("JWT_ALG", "HS256")
    os.environ.setdefault("JWT_EXP_MIN", "60")
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
    # usuń stary plik jeżeli był
    if TEST_DB.exists():
        TEST_DB.unlink()
    yield
    # sprzątanie po całej sesji testowej
    try:
        # zrzucenie uchwytów do pliku przed usunięciem
        from api import db as dbmod
        dbmod.engine.dispose()
    except Exception:
        pass
    if TEST_DB.exists():
        TEST_DB.unlink()

@pytest.fixture(scope="session")
def client():
    from api.main_api import app
    with TestClient(app) as c:
        # seed admina
        r = c.post("/jwt/seed_admin")
        assert r.status_code in (200, 201)
        yield c

@pytest.fixture
def admin_token(client: TestClient) -> str:
    r = client.post("/jwt/login_form", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]

@pytest.fixture
def admin_auth(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
