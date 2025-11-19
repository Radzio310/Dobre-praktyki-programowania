import types
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main_api import app
from api.db import Base, Rating as RatingModel
import api.ratings as ratings_module
from jwt import deps as jwt_deps


# ==============================
# Fixtury: DB + auth + client
# ==============================

@pytest.fixture()
def test_db_engine():
    # Używamy jednej "wspólnej" bazy in-memory dla wszystkich połączeń w testach
    engine = create_engine(
        "sqlite://",  # UWAGA: bez /:memory:
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()



@pytest.fixture()
def TestSessionLocal(test_db_engine):
    return sessionmaker(bind=test_db_engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture()
def db_session(TestSessionLocal):
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def auth_override():
    def fake_get_current_user():
        return types.SimpleNamespace(sub="test-user", roles=["ROLE_USER"])

    app.dependency_overrides[jwt_deps.get_current_user] = fake_get_current_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(jwt_deps.get_current_user, None)


@pytest.fixture()
def client(db_session, TestSessionLocal, auth_override):
    # nadpisujemy get_db z modułu ratings
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[ratings_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(ratings_module.get_db, None)


# ==============================
# Fixtury danych
# ==============================

@pytest.fixture()
def ratings_seed(db_session):
    """Kilka ocen do testu listy."""
    objs = [
        RatingModel(userId=1, movieId=10, rating=4.0, timestamp=1111111111),
        RatingModel(userId=2, movieId=20, rating=3.5, timestamp=2222222222),
        RatingModel(userId=3, movieId=30, rating=5.0, timestamp=3333333333),
    ]
    db_session.add_all(objs)
    db_session.commit()
    # zwracamy liczbę jako referencję do porównania
    return len(objs)


@pytest.fixture()
def single_rating(db_session):
    """Pojedyncza ocena do testów GET/PUT/DELETE."""
    r = RatingModel(userId=99, movieId=42, rating=2.5, timestamp=4444444444)
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r.id


# ==============================
# TESTY
# ==============================

def test_list_ratings_returns_all(client, ratings_seed):
    r = client.get("/ratings")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == ratings_seed
    for item in data:
        assert "id" in item
        assert "userId" in item
        assert "movieId" in item
        assert "rating" in item
        assert "timestamp" in item


def test_get_rating_by_id_ok(client, single_rating):
    r = client.get(f"/ratings/{single_rating}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == single_rating
    assert data["userId"] == 99
    assert data["movieId"] == 42
    assert data["rating"] == 2.5
    assert data["timestamp"] == 4444444444


def test_get_rating_by_id_404(client):
    r = client.get("/ratings/999999")
    assert r.status_code == 404
    data = r.json()
    assert "detail" in data
    assert data["detail"] == "Rating not found"


def test_post_rating_creates_new(client):
    payload = {
        "userId": 7,
        "movieId": 77,
        "rating": 4.5,
        "timestamp": 5555555555,
    }
    r = client.post("/ratings", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert "id" in created
    assert created["userId"] == payload["userId"]
    assert created["movieId"] == payload["movieId"]
    assert created["rating"] == payload["rating"]
    assert created["timestamp"] == payload["timestamp"]

    # potwierdzamy, że pojawił się na liście
    r2 = client.get("/ratings")
    ids = [item["id"] for item in r2.json()]
    assert created["id"] in ids


def test_put_rating_updates(client, single_rating):
    update_payload = {
        "rating": 3.0,
        "timestamp": 6666666666,
    }
    r = client.put(f"/ratings/{single_rating}", json=update_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == single_rating
    assert data["rating"] == 3.0
    assert data["timestamp"] == 6666666666

    # sprawdzamy GET-em po zmianie
    r2 = client.get(f"/ratings/{single_rating}")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["rating"] == 3.0
    assert data2["timestamp"] == 6666666666


def test_delete_rating_removes(client, single_rating):
    r = client.delete(f"/ratings/{single_rating}")
    assert r.status_code == 204
    assert r.content in (b"", None)

    # po usunięciu powinien zwrócić 404
    r2 = client.get(f"/ratings/{single_rating}")
    assert r2.status_code == 404
