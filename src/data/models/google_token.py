"""
SQLAlchemy model for per-user Google OAuth tokens.

One row per user.  The `token_json` column stores the full JSON blob
that `google.oauth2.credentials.Credentials.to_json()` produces, so
the token can be restored with `Credentials.from_authorized_user_info`.

On row conflict (user already has a token) the UPSERT in
`google_oauth_service.save_token` replaces the existing row.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.data.database import Base


class GoogleToken(Base):
    __tablename__ = "google_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,  # one token per user
    )
    token_json: Mapped[str] = mapped_column(Text, nullable=False)
    google_email: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
