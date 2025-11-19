import types
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.main_api import app
from api.db import Base, Movie
import api.movies as movies_module  # żeby nadpisać movies_module.get_db
from jwt import deps as jwt_deps    # żeby nadpisać get_current_user


# =========================================================
# Fixtury infrastrukturalne (DB + auth + client)
# =========================================================

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
    # Prosty „użytkownik” przechodzący autoryzację
    def fake_get_current_user():
        return types.SimpleNamespace(sub="test-user", roles=["ROLE_USER"])
    # Nadpisujemy globalną zależność używaną przy include_router(...)
    app.dependency_overrides[jwt_deps.get_current_user] = fake_get_current_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(jwt_deps.get_current_user, None)


@pytest.fixture()
def client(db_session, TestSessionLocal, auth_override):
    # Nadpisanie get_db w module routera filmów
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[movies_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(movies_module.get_db, None)


# =========================================================
# Fixtury danych dla endpointów
# =========================================================

@pytest.fixture()
def movies_seed(db_session):
    """Seed minimalny do testów GET /movies i GET /movies/{id}."""
    db_session.add_all([
        Movie(movieId=1, title="Movie One", genres="Action|Thriller"),
        Movie(movieId=2, title="Movie Two", genres="Comedy"),
        Movie(movieId=3, title="Movie Three", genres="Drama"),
    ])
    db_session.commit()
    return [1, 2, 3]


@pytest.fixture()
def single_movie(db_session):
    """Pojedynczy film do testów GET item / PUT / DELETE."""
    m = Movie(movieId=10, title="Ten", genres="Sci-Fi")
    db_session.add(m)
    db_session.commit()
    return 10


# =========================================================
# TESTY
# Każdy endpoint ma jeden test, ale z kilkoma asercjami.
# =========================================================

def test_list_movies_returns_all(client, movies_seed):
    # WHEN
    r = client.get("/movies")
    # THEN
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == len(movies_seed)
    # Porównaj ID-y bez porządku
    ids = sorted(m["movieId"] for m in data)
    assert ids == sorted(movies_seed)


def test_get_movie_by_id_ok(client, single_movie):
    r = client.get(f"/movies/{single_movie}")
    assert r.status_code == 200
    data = r.json()
    assert data["movieId"] == single_movie
    assert data["title"] == "Ten"
    assert data["genres"] == "Sci-Fi"


def test_get_movie_by_id_404(client):
    r = client.get("/movies/999999")
    assert r.status_code == 404
    data = r.json()
    assert "detail" in data
    assert data["detail"] == "Movie not found"


def test_post_movie_creates_new(client):
    payload = {"movieId": 123, "title": "New Movie", "genres": "Adventure"}
    r = client.post("/movies", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert created["movieId"] == 123
    assert created["title"] == "New Movie"
    assert created["genres"] == "Adventure"

    # Potwierdź obecność na liście
    r2 = client.get("/movies")
    assert r2.status_code == 200
    ids = [m["movieId"] for m in r2.json()]
    assert 123 in ids

    # Próba duplikatu -> 409
    r3 = client.post("/movies", json=payload)
    assert r3.status_code == 409


def test_put_movie_updates(client, single_movie):
    # Zmiana tytułu i gatunków
    update = {"title": "Ten (Updated)", "genres": "Sci-Fi|Mystery"}
    r = client.put(f"/movies/{single_movie}", json=update)
    assert r.status_code == 200
    data = r.json()
    assert data["movieId"] == single_movie
    assert data["title"] == "Ten (Updated)"
    assert data["genres"] == "Sci-Fi|Mystery"

    # Potwierdź GET-em
    r2 = client.get(f"/movies/{single_movie}")
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["title"] == "Ten (Updated)"
    assert data2["genres"] == "Sci-Fi|Mystery"


def test_delete_movie_removes(client, single_movie):
    # Usunięcie
    r = client.delete(f"/movies/{single_movie}")
    assert r.status_code == 204
    assert r.content in (b"", None)  # 204 -> body puste

    # Nie powinno już być
    r2 = client.get(f"/movies/{single_movie}")
    assert r2.status_code == 404
