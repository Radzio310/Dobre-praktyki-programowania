from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.db import Session as DBSession, Movie

router = APIRouter(tags=["Movies"])


# =========================
# Schematy Pydantic
# =========================

class MovieOut(BaseModel):
    movieId: int
    title: str
    genres: str

    class Config:
        orm_mode = True


class MovieCreate(BaseModel):
    movieId: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    genres: str = Field(..., min_length=1)


class MovieUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    genres: Optional[str] = Field(None, min_length=1)


# =========================
# Dependency: sesja DB
# =========================
def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


# =========================
# Endpoints
# =========================

@router.get("/movies", response_model=List[MovieOut])
def get_movies(db: Session = Depends(get_db)):
    """Lista filmów."""
    return db.query(Movie).all()


@router.post(
    "/movies",
    response_model=MovieOut,
    status_code=status.HTTP_201_CREATED,
)
def create_movie(payload: MovieCreate, db: Session = Depends(get_db)):
    """Utwórz nowy film."""
    # Sprawdzenie duplikatu klucza głównego
    exists = db.query(Movie).filter(Movie.movieId == payload.movieId).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Movie with id {payload.movieId} already exists",
        )
    obj = Movie(movieId=payload.movieId, title=payload.title, genres=payload.genres)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/movies/{movie_id}", response_model=MovieOut)
def get_movie(movie_id: int, db: Session = Depends(get_db)):
    """Pobierz pojedynczy film."""
    obj = db.query(Movie).filter(Movie.movieId == movie_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    return obj


@router.put("/movies/{movie_id}", response_model=MovieOut)
def update_movie(movie_id: int, payload: MovieUpdate, db: Session = Depends(get_db)):
    """Aktualizuj film (title/genres)."""
    obj = db.query(Movie).filter(Movie.movieId == movie_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    if payload.title is not None:
        obj.title = payload.title
    if payload.genres is not None:
        obj.genres = payload.genres

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/movies/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int, db: Session = Depends(get_db)):
    """Usuń film."""
    obj = db.query(Movie).filter(Movie.movieId == movie_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")
    db.delete(obj)
    db.commit()
    # 204 - No Content
    return None
