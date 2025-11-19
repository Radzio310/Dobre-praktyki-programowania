from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as OrmSession

from api.db import Session as DBSession, Rating as RatingModel

router = APIRouter(tags=["Ratings"])


# ============== Schematy Pydantic ==============

class RatingOut(BaseModel):
    id: int
    userId: int
    movieId: int
    rating: float
    timestamp: int

    class Config:
        orm_mode = True


class RatingCreate(BaseModel):
    userId: int = Field(..., ge=1)
    movieId: int = Field(..., ge=1)
    rating: float = Field(..., ge=0.0, le=5.0)
    timestamp: int = Field(..., ge=0)


class RatingUpdate(BaseModel):
    userId: Optional[int] = Field(None, ge=1)
    movieId: Optional[int] = Field(None, ge=1)
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    timestamp: Optional[int] = Field(None, ge=0)


# ============== Dependency: sesja DB ==============

def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


# ============== Endpoints ==============

@router.get("/ratings", response_model=List[RatingOut])
def get_ratings(db: OrmSession = Depends(get_db)):
    """Lista wszystkich ocen."""
    return db.query(RatingModel).all()


@router.post(
    "/ratings",
    response_model=RatingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_rating(payload: RatingCreate, db: OrmSession = Depends(get_db)):
    """Utwórz nową ocenę."""
    obj = RatingModel(
        userId=payload.userId,
        movieId=payload.movieId,
        rating=payload.rating,
        timestamp=payload.timestamp,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/ratings/{rating_id}", response_model=RatingOut)
def get_rating(rating_id: int, db: OrmSession = Depends(get_db)):
    """Pobierz pojedynczą ocenę po ID."""
    obj = db.query(RatingModel).filter(RatingModel.id == rating_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")
    return obj


@router.put("/ratings/{rating_id}", response_model=RatingOut)
def update_rating(
    rating_id: int,
    payload: RatingUpdate,
    db: OrmSession = Depends(get_db),
):
    """Aktualizuj ocenę."""
    obj = db.query(RatingModel).filter(RatingModel.id == rating_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")

    if payload.userId is not None:
        obj.userId = payload.userId
    if payload.movieId is not None:
        obj.movieId = payload.movieId
    if payload.rating is not None:
        obj.rating = payload.rating
    if payload.timestamp is not None:
        obj.timestamp = payload.timestamp

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/ratings/{rating_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rating(rating_id: int, db: OrmSession = Depends(get_db)):
    """Usuń ocenę."""
    obj = db.query(RatingModel).filter(RatingModel.id == rating_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rating not found")

    db.delete(obj)
    db.commit()
    return None  # 204 – puste body
