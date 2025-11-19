# api/users.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import Session as DBSession, User
from jwt.deps import get_current_user, require_roles
from jwt.crypto import hash_password

router = APIRouter(tags=["Users"])


def get_db():
    with DBSession() as s:
        yield s


class CreateUserIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=3)
    roles: List[str] = []  # np. ["ROLE_ADMIN", "ROLE_USER"]


class UserOut(BaseModel):
    id: int
    username: str
    roles: List[str]


class MeOut(BaseModel):
    sub: str
    roles: List[str]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("ROLE_ADMIN"))],
)
def create_user(data: CreateUserIn, db: Session = Depends(get_db)):
    # unikalny username
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username_exists")

    roles_csv = ",".join(sorted(set(r.strip() for r in data.roles if r.strip())))
    u = User(username=data.username, password_hash=hash_password(data.password), roles=roles_csv)
    db.add(u)
    db.commit()
    db.refresh(u)

    roles_list = [r.strip() for r in (u.roles or "").split(",") if r.strip()]
    return UserOut(id=u.id, username=u.username, roles=roles_list)


@router.get("/user_details", response_model=MeOut)
def user_details(user = Depends(get_current_user)):
    # zwracamy pola bezpośrednio z payloadu JWT
    return MeOut(sub=user.sub, roles=user.roles)
