from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as OrmSession

from api.db import Session as DBSession, Tag as TagModel

router = APIRouter(tags=["Tags"])


# ============== Schematy Pydantic ==============

class TagOut(BaseModel):
    id: int
    userId: int
    movieId: int
    tag: str
    timestamp: int

    class Config:
        orm_mode = True


class TagCreate(BaseModel):
    userId: int = Field(..., ge=1)
    movieId: int = Field(..., ge=1)
    tag: str = Field(..., min_length=1)
    timestamp: int = Field(..., ge=0)


class TagUpdate(BaseModel):
    userId: Optional[int] = Field(None, ge=1)
    movieId: Optional[int] = Field(None, ge=1)
    tag: Optional[str] = Field(None, min_length=1)
    timestamp: Optional[int] = Field(None, ge=0)


# ============== Dependency: sesja DB ==============

def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


# ============== Endpoints ==============

@router.get("/tags", response_model=List[TagOut])
def get_tags(db: OrmSession = Depends(get_db)):
    """Lista wszystkich tagów."""
    return db.query(TagModel).all()


@router.post(
    "/tags",
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
)
def create_tag(payload: TagCreate, db: OrmSession = Depends(get_db)):
    """Utwórz nowy tag."""
    obj = TagModel(
        userId=payload.userId,
        movieId=payload.movieId,
        tag=payload.tag,
        timestamp=payload.timestamp,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/tags/{tag_id}", response_model=TagOut)
def get_tag(tag_id: int, db: OrmSession = Depends(get_db)):
    """Pobierz pojedynczy tag po ID."""
    obj = db.query(TagModel).filter(TagModel.id == tag_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return obj


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: OrmSession = Depends(get_db),
):
    """Aktualizuj tag."""
    obj = db.query(TagModel).filter(TagModel.id == tag_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if payload.userId is not None:
        obj.userId = payload.userId
    if payload.movieId is not None:
        obj.movieId = payload.movieId
    if payload.tag is not None:
        obj.tag = payload.tag
    if payload.timestamp is not None:
        obj.timestamp = payload.timestamp

    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: OrmSession = Depends(get_db)):
    """Usuń tag."""
    obj = db.query(TagModel).filter(TagModel.id == tag_id).first()
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    db.delete(obj)
    db.commit()
    return None  # 204 – puste body
