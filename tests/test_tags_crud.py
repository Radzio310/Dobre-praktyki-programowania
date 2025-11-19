import types
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main_api import app
from api.db import Base, Tag as TagModel
import api.tags as tags_module
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
    # nadpisujemy get_db z modułu tags
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[tags_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(tags_module.get_db, None)


# ==============================
# Fixtury danych
# ==============================

@pytest.fixture()
def tags_seed(db_session):
    """Kilka tagów do testu listy."""
    objs = [
        TagModel(userId=1, movieId=10, tag="funny", timestamp=1111111111),
        TagModel(userId=2, movieId=20, tag="boring", timestamp=2222222222),
        TagModel(userId=3, movieId=30, tag="classic", timestamp=3333333333),
    ]
    db_session.add_all(objs)
    db_session.commit()
    return len(objs)


@pytest.fixture()
def single_tag(db_session):
    """Pojedynczy tag do testów GET/PUT/DELETE."""
    t = TagModel(userId=99, movieId=42, tag="old", timestamp=4444444444)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t.id


# ==============================
# TESTY
# ==============================

def test_list_tags_returns_all(client, tags_seed):
    r = client.get("/tags")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == tags_seed
    for item in data:
        assert "id" in item
        assert "userId" in item
        assert "movieId" in item
        assert "tag" in item
        assert "timestamp" in item


def test_get_tag_by_id_ok(client, single_tag):
    r = client.get(f"/tags/{single_tag}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == single_tag
    assert data["userId"] == 99
    assert data["movieId"] == 42
    assert data["tag"] == "old"
    assert data["timestamp"] == 4444444444


def test_get_tag_by_id_404(client):
    r = client.get("/tags/999999")
    assert r.status_code == 404
    data = r.json()
    assert "detail" in data
    assert data["detail"] == "Tag not found"


def test_post_tag_creates_new(client):
    payload = {
        "userId": 7,
        "movieId": 77,
        "tag": "awesome",
        "timestamp": 5555555555,
    }
    r = client.post("/tags", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert "id" in created
    assert created["userId"] == payload["userId"]
    assert created["movieId"] == payload["movieId"]
    assert created["tag"] == payload["tag"]
    assert created["timestamp"] == payload["timestamp"]

    # potwierdzamy, że pojawił się na liście
    r2 = client.get("/tags")
    ids = [item["id"] for item in r2.json()]
    assert created["id"] in ids


def test_put_tag_updates(client, single_tag):
    update_payload = {
        "tag": "updated",
        "timestamp": 6666666666,
    }
    r = client.put(f"/tags/{single_tag}", json=update_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == single_tag
    assert data["tag"] == "updated"
    assert data["timestamp"] == 6666666666

    # sprawdzamy GET-em po zmianie
    r2 = client.get(f"/tags/{single_tag}")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["tag"] == "updated"
    assert data2["timestamp"] == 6666666666


def test_delete_tag_removes(client, single_tag):
    r = client.delete(f"/tags/{single_tag}")
    assert r.status_code == 204
    assert r.content in (b"", None)

    # po usunięciu powinien zwrócić 404
    r2 = client.get(f"/tags/{single_tag}")
    assert r2.status_code == 404
