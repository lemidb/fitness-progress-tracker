from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Boolean,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    muscle_group: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False, default="strength")
    default_weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=50)
    default_sets: Mapped[int] = mapped_column(Integer, default=3)
    default_reps: Mapped[int] = mapped_column(Integer, default=10)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"
    __table_args__ = (UniqueConstraint("id", "user_id", name="uq_workout_sessions_id_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mood: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    energy: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    sleep_quality: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    bodyweight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    entries: Mapped[list["WorkoutLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkoutLog(Base):
    __tablename__ = "workout_logs"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_workout_logs_id_user"),
        ForeignKeyConstraint(
            ["session_id", "user_id"],
            ["workout_sessions.id", "workout_sessions.user_id"],
            ondelete="CASCADE",
            name="fk_workout_logs_session_owner",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    exercise_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("exercises.id", ondelete="SET NULL")
    )
    exercise: Mapped[str] = mapped_column(String(100), nullable=False)
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False, default="strength")
    muscle_group: Mapped[str] = mapped_column(String(32), nullable=False, default="full_body")
    sets_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    form_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    range_of_motion: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    device_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[WorkoutSession] = relationship(back_populates="entries")
    sets: Mapped[list["WorkoutSet"]] = relationship(
        back_populates="workout_log", cascade="all, delete-orphan", lazy="selectin"
    )


class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["log_id", "user_id"],
            ["workout_logs.id", "workout_logs.user_id"],
            ondelete="CASCADE",
            name="fk_workout_sets_log_owner",
        ),
        UniqueConstraint("log_id", "set_number", name="uq_workout_sets_log_set_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    log_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    rpe: Mapped[Decimal | None] = mapped_column(Numeric(3, 1))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workout_log: Mapped[WorkoutLog] = relationship(back_populates="sets")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("user_id", "provider_event_id", name="uq_calendar_events_user_provider_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    exercise_type: Mapped[str] = mapped_column(String(32), nullable=False, default="strength")
    estimated_duration_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    estimated_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_insights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    provider_event_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GoogleCalendarConnection(Base):
    __tablename__ = "google_calendar_connections"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    account_email: Mapped[str | None] = mapped_column(String(320))
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))