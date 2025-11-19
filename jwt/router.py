# jwt/router.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session

from api.db import Session as DBSession
from api.db import User

from .crypto import verify_password, hash_password
from .tokens import create_access_token
from .deps import get_current_user

router = APIRouter(prefix="/jwt", tags=["auth"])


def get_db():
    # Sesja zgodna z resztą aplikacji
    with DBSession() as s:
        yield s


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    sub: str
    roles: List[str]


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user: User | None = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")

    roles = user.roles if isinstance(user.roles, list) else (user.roles or "").split(",")
    roles = [r.strip() for r in roles if r.strip()]

    token = create_access_token(sub=str(user.id), roles=roles)
    return TokenResponse(access_token=token)


@router.post("/login_form", response_model=TokenResponse)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2 password flow: username/password jako application/x-www-form-urlencoded
    user: User | None = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")
    roles = (user.roles or "").split(",")
    roles = [r.strip() for r in roles if r.strip()]
    token = create_access_token(sub=str(user.id), roles=roles)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(user = Depends(get_current_user)):
    return MeResponse(sub=user.sub, roles=user.roles)


@router.post("/seed_admin", status_code=201)
def seed_admin(db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        return {"status": "exists"}

    u = User(username="admin", password_hash=hash_password("admin"), roles="ROLE_ADMIN")
    db.add(u)
    db.commit()
    return {"status": "created", "username": "admin", "password": "admin"}
