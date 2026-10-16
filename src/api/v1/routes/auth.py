"""Profile endpoint backed by the verified Supabase Auth identity."""
from __future__ import annotations

from typing import Annotated

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import get_current_user, get_supabase_user
from src.data.database import get_db
from src.data.models.fitness import GoogleCalendarConnection

router = APIRouter(prefix="/auth", tags=["auth"])


class UserProfile(BaseModel):
    user_id: str
    username: str | None = None
    email: str | None = None


@router.get("/me", response_model=UserProfile)
async def me(user: Annotated[dict, Depends(get_supabase_user)]) -> UserProfile:
    """Return the currently authenticated Supabase user profile."""
    metadata = user.get("user_metadata") or {}
    return UserProfile(
        user_id=str(user["id"]),
        username=metadata.get("username") or metadata.get("name"),
        email=user.get("email"),
    )


class GoogleCalendarConnectionStatus(BaseModel):
    connected: bool
    account_email: str | None = None
    connected_at: datetime | None = None
    last_synced_at: datetime | None = None


@router.get("/connections")
async def connections(
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Return the last successfully verified Google Calendar connection state."""
    result = await db.execute(
        select(GoogleCalendarConnection).where(
            GoogleCalendarConnection.user_id == UUID(current_user)
        )
    )
    connection = result.scalar_one_or_none()
    return {
        "google_calendar": GoogleCalendarConnectionStatus(
            connected=bool(connection and connection.is_connected),
            account_email=connection.account_email if connection else None,
            connected_at=connection.connected_at if connection else None,
            last_synced_at=connection.last_synced_at if connection else None,
        )
    }
