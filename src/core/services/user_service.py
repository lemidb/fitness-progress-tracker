from __future__ import annotations

import uuid

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.user import User

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hashes a plain-text password using the configured scheme (Argon2)."""
    # Passlib is sensitive to the input type.
    # It's most reliable when given bytes. We encode the plain-text string to UTF-8 bytes.
    hashed_password = pwd_context.hash(password.encode("utf-8"))
    return hashed_password


def verify_password(plain_password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(
        select(User).where(User.external_id == username)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
    email: str | None = None,
) -> User:
    user = User(
        external_id=username,
        email=email,
        password_hash=hash_password(password),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ValueError("user already exists") from exc
    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    username: str,
    password: str,
) -> User | None:
    user = await get_user_by_username(session, username)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
