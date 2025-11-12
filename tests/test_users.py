# tests/test_users.py
from fastapi.testclient import TestClient

def test_create_user_admin_only(client: TestClient, admin_auth: dict):
    payload = {"username": "alice", "password": "secret", "roles": ["ROLE_USER"]}
    r = client.post("/users", json=payload, headers=admin_auth)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["id"] > 0
    assert data["username"] == "alice"
    assert data["roles"] == ["ROLE_USER"]

def test_create_user_forbidden_without_admin(client: TestClient):
    # brak tokena admina -> 401/403
    payload = {"username": "bob", "password": "x", "roles": ["ROLE_USER"]}
    r = client.post("/users", json=payload)
    assert r.status_code in (401, 403)

def test_user_can_login_and_get_user_details(client: TestClient, admin_auth: dict):
    # najpierw stwórz zwykłego usera
    client.post("/users", json={"username": "charlie", "password": "pwd", "roles": ["ROLE_USER"]}, headers=admin_auth)
    # login tego usera
    r = client.post("/jwt/login_form", data={"username": "charlie", "password": "pwd"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    # /user_details zwraca dane z JWT
    r2 = client.get("/user_details", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["sub"]  # id użytkownika
    assert "ROLE_USER" in body["roles"]


def test_user_details_requires_token(client: TestClient):
    r = client.get("/user_details")  # brak Authorization
    assert r.status_code in (401, 403)