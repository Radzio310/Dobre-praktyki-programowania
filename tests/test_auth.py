# tests/test_auth.py
from fastapi.testclient import TestClient


def test_login_form_and_me(client: TestClient):
    r = client.post("/jwt/login_form", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r2 = client.get("/jwt/me", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    data = r2.json()
    assert data["sub"]  # id admina
    assert "ROLE_ADMIN" in data["roles"]

def test_protected_requires_auth(client: TestClient):
    r = client.get("/movies")  # router chroniony globalnie
    assert r.status_code in (401, 403)

def test_secure_ping_ok(client: TestClient):
    r = client.post("/jwt/login_form", data={"username": "admin", "password": "admin"})
    token = r.json()["access_token"]
    r2 = client.get("/secure/ping", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert r2.json()["ok"] is True

def test_login_bad_credentials(client: TestClient, username, password):
    r = client.post("/jwt/login_form", data={"username": username, "password": password})
    assert r.status_code == 401

def test_login_missing_fields(client: TestClient):
    r = client.post("/jwt/login_form", data={"username": "admin"})  # bez password
    assert r.status_code in (400, 422)
    r2 = client.post("/jwt/login_form", data={"password": "admin"})  # bez username
    assert r2.status_code in (400, 422)