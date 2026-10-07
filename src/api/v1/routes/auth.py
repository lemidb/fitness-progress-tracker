"""
Auth routes backed by PostgreSQL.
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import (
    TokenPair,
    create_token_pair,
    decode_token,
    get_current_user,
)
from src.core.services import user_service
from src.data.database import get_db
from src.data.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

DEV_SECRET = "dev"


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenRequest(BaseModel):
    user_id: str
    secret: str = ""


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterResponse(BaseModel):
    user_id: str
    username: str
    status: str = "created"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserProfile(BaseModel):
    user_id: str
    username: str
    email: str | None = None


def _tokens_for_user(user: User) -> TokenPair:
    return create_token_pair(str(user.id))


@router.post("/register", response_model=RegisterResponse)
async def register(
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new user in PostgreSQL and return JWT tokens."""
    if not payload.username.strip() or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username and password are required",
        )

    existing = await user_service.get_user_by_username(session, payload.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            
            detail="user already exists",
        )

    try:
        user = await user_service.create_user(
            session=session,
            username=payload.username,
            password=payload.password,
            email=payload.email
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    tokens = _tokens_for_user(user)
    return RegisterResponse(
        user_id=str(user.id),
        username=user.external_id,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Validate credentials against PostgreSQL and issue JWT tokens."""
    user = await user_service.authenticate_user(
        session,
        username=payload.username,
        password=payload.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )
    return _tokens_for_user(user)


@router.post("/token", response_model=TokenPair)
async def get_token(
    payload: TokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Development-only token route.
    POST /auth/token
    {"user_id": "<uuid-or-username>", "secret": "dev"}
    """
    if payload.secret != DEV_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid secret for dev token",
        )

    user = await _resolve_user(session, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    return _tokens_for_user(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    payload: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Exchange a refresh token for a new token pair."""
    token_data = decode_token(payload.refresh_token)
    try:
        user_id = uuid.UUID(token_data.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token"
        ) from exc
    user = await user_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists",
        )
    return _tokens_for_user(user)


@router.get("/me", response_model=UserProfile)
async def me(
    current_user: Annotated[str, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """Return the authenticated user's profile from PostgreSQL."""
    try:
        user_id = uuid.UUID(current_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token"
        ) from exc
    user = await user_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user no longer exists",
        )
    return UserProfile(
        user_id=str(user.id),
        username=user.external_id,
        email=user.email,
    )


async def _resolve_user(session: AsyncSession, user_ref: str) -> User | None:
    """
    Find a user by either UUID or username.
    Primarily for use by the development /token endpoint.
    """
    try:
        # Try parsing as UUID first
        user_id = uuid.UUID(user_ref)
        return await user_service.get_user_by_id(session, user_id)
    except ValueError:
        # Fall back to username if not a valid UUID
        return await user_service.get_user_by_username(session, user_ref)
