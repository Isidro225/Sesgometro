from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User
from app.schemas import AuthResponse, LoginRequest, SignupRequest, UserPublic
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _to_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at)


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, session: Annotated[Session, Depends(get_session)]) -> AuthResponse:
    email = payload.email.lower().strip()
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una cuenta con ese email.")
    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthResponse(access_token=create_access_token(user.id), user=_to_public(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, session: Annotated[Session, Depends(get_session)]) -> AuthResponse:
    email = payload.email.lower().strip()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas.")
    return AuthResponse(access_token=create_access_token(user.id), user=_to_public(user))


@router.get("/me", response_model=UserPublic)
def me(current_user: Annotated[User, Depends(get_current_user)]) -> UserPublic:
    return _to_public(current_user)
