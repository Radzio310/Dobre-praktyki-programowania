from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as OrmSession

from api.db import Session as DBSession, Link as LinkModel

router = APIRouter(tags=["Links"])


# ============== Schematy Pydantic ==============

class LinkOut(BaseModel):
    movieId: int
    imdbId: Optional[str] = None
    tmdbId: Optional[str] = None

    class Config:
        orm_mode = True


class LinkCreate(BaseModel):
    movieId: int = Field(..., ge=1)
    imdbId: Optional[str] = None
    tmdbId: Optional[str] = None


class LinkUpdate(BaseModel):
    imdbId: Optional[str] = None
    tmdbId: Optional[str] = None


# ============== Dependency: sesja DB ==============

def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


# ============== Endpoints ==============

@router.get("/links", response_model=List[LinkOut])
def get_links(db: OrmSession = Depends(get_db)):
    """Lista wszystkich linków."""
    return db.query(LinkModel).all()


@router.post(
    "/links",
    response_model=LinkOut,
    status_code=status.HTTP_201_CREATED,
)
def create_link(payload: LinkCreate, db: OrmSession = Depends(get_db)):
    """Utwórz nowy link dla filmu."""
    exists = db.query(LinkModel).filter(LinkModel.movieId == payload.movieId).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Link for movieId {payload.movieId} already exists",
        )
    obj = LinkModel(
        movieId=payload.movieId,
        imdbId=payload.imdbId,
        tmdbId=payload.tmdbId,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/links/{movie_id}", response_model=LinkOut)
def get_link(movie_id: int, db: OrmSession = Depends(get_db)):
    """Pobierz link po movieId."""
    obj = db.query(LinkModel).filter(LinkModel.movieId == movie_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    return obj


@router.put("/links/{movie_id}", response_model=LinkOut)
def update_link(
    movie_id: int,
    payload: LinkUpdate,
    db: OrmSession = Depends(get_db),
):
    """Aktualizuj link (imdbId/tmdbId) dla danego movieId."""
    obj = db.query(LinkModel).filter(LinkModel.movieId == movie_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    if payload.imdbId is not None:
        obj.imdbId = payload.imdbId
    if payload.tmdbId is not None:
        obj.tmdbId = payload.tmdbId

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/links/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(movie_id: int, db: OrmSession = Depends(get_db)):
    """Usuń link dla danego movieId."""
    obj = db.query(LinkModel).filter(LinkModel.movieId == movie_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    db.delete(obj)
    db.commit()
    return None  # 204 – puste body
