import types
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main_api import app
from api.db import Base, Link as LinkModel
import api.links as links_module
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
    # nadpisujemy get_db z modułu links
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[links_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(links_module.get_db, None)


# ==============================
# Fixtury danych
# ==============================

@pytest.fixture()
def links_seed(db_session):
    """Kilka linków do testu listy."""
    objs = [
        LinkModel(movieId=10, imdbId="tt0010", tmdbId="100"),
        LinkModel(movieId=20, imdbId="tt0020", tmdbId="200"),
        LinkModel(movieId=30, imdbId="tt0030", tmdbId="300"),
    ]
    db_session.add_all(objs)
    db_session.commit()
    return len(objs)


@pytest.fixture()
def single_link(db_session):
    """Pojedynczy link do testów GET/PUT/DELETE."""
    l = LinkModel(movieId=42, imdbId="tt0042", tmdbId="420")
    db_session.add(l)
    db_session.commit()
    # PK = movieId, więc zwracamy movieId
    return 42


# ==============================
# TESTY
# ==============================

def test_list_links_returns_all(client, links_seed):
    r = client.get("/links")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == links_seed
    for item in data:
        assert "movieId" in item
        assert "imdbId" in item
        assert "tmdbId" in item


def test_get_link_by_movie_id_ok(client, single_link):
    r = client.get(f"/links/{single_link}")
    assert r.status_code == 200
    data = r.json()
    assert data["movieId"] == single_link
    assert data["imdbId"] == "tt0042"
    assert data["tmdbId"] == "420"


def test_get_link_by_movie_id_404(client):
    r = client.get("/links/999999")
    assert r.status_code == 404
    data = r.json()
    assert "detail" in data
    assert data["detail"] == "Link not found"


def test_post_link_creates_new(client):
    payload = {
        "movieId": 77,
        "imdbId": "tt0077",
        "tmdbId": "770",
    }
    r = client.post("/links", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert created["movieId"] == payload["movieId"]
    assert created["imdbId"] == payload["imdbId"]
    assert created["tmdbId"] == payload["tmdbId"]

    # potwierdzamy, że pojawił się na liście
    r2 = client.get("/links")
    ids = [item["movieId"] for item in r2.json()]
    assert payload["movieId"] in ids

    # próba duplikatu -> 409
    r3 = client.post("/links", json=payload)
    assert r3.status_code == 409


def test_put_link_updates(client, single_link):
    update_payload = {
        "imdbId": "tt9999",
        "tmdbId": "999",
    }
    r = client.put(f"/links/{single_link}", json=update_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["movieId"] == single_link
    assert data["imdbId"] == "tt9999"
    assert data["tmdbId"] == "999"

    # sprawdzamy GET-em po zmianie
    r2 = client.get(f"/links/{single_link}")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["imdbId"] == "tt9999"
    assert data2["tmdbId"] == "999"


def test_delete_link_removes(client, single_link):
    r = client.delete(f"/links/{single_link}")
    assert r.status_code == 204
    assert r.content in (b"", None)

    # po usunięciu powinien zwrócić 404
    r2 = client.get(f"/links/{single_link}")
    assert r2.status_code == 404
