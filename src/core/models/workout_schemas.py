from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.core.models.domain import ExerciseType, MuscleGroup


class WorkoutSetInput(BaseModel):
    reps: int = Field(ge=0, le=1000)
    weight_kg: float = Field(ge=0, le=1000)
    rpe: float | None = Field(None, ge=1, le=10)


class WorkoutEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise: str = Field(min_length=2, max_length=100)
    exercise_id: str | None = Field(None, max_length=100)
    sets: list[WorkoutSetInput] = Field(min_length=1, max_length=100)
    rpe: float | None = Field(None, ge=1, le=10)
    exercise_type: ExerciseType = ExerciseType.STRENGTH
    muscle_group: MuscleGroup = MuscleGroup.FULL_BODY
    notes: str = Field(default="", max_length=2000)
    form_score: float | None = Field(None, ge=0, le=10)
    range_of_motion: float | None = Field(None, ge=0, le=100)
    device_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("exercise")
    @classmethod
    def normalize_exercise(cls, value: str) -> str:
        return value.strip()


class SessionMetadataInput(BaseModel):
    mood: int = Field(default=8, ge=1, le=10)
    energy: int = Field(default=8, ge=1, le=10)
    sleep_quality: int = Field(default=8, ge=1, le=10)
    bodyweight_kg: float | None = Field(None, ge=20, le=300)
    notes: str = Field(default="", max_length=2000)


class WorkoutLogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[WorkoutEntryInput] = Field(min_length=1, max_length=100)
    session_metadata: SessionMetadataInput = Field(default_factory=SessionMetadataInput)
    started_at: datetime | None = None


class EntryInsight(BaseModel):
    exercise: str
    is_pr: bool
    prev_max_kg: float
    form_quality: str
    suggestion: str


class WorkoutLogResponse(BaseModel):
    status: str = "success"
    session_id: str
    logged_entries: int
    total_volume: float
    insights: list[EntryInsight]
    timestamp: str


class ExerciseResponse(BaseModel):
    id: str
    name: str
    muscle_group: str
    exercise_type: str
    default_weight_kg: float
    default_sets: int
    default_reps: int


class ExerciseCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    muscle_group: MuscleGroup
    exercise_type: ExerciseType = ExerciseType.STRENGTH
    default_weight_kg: float = Field(default=50, ge=0, le=1000)
    default_sets: int = Field(default=3, ge=1, le=100)
    default_reps: int = Field(default=10, ge=1, le=1000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()
