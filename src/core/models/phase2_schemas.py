from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CalendarEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    start: datetime
    end: datetime
    description: str = Field(default="", max_length=5000)
    location: str = Field(default="", max_length=500)
    type: Literal["strength", "cardio", "flexibility", "mixed"] = "strength"
    estimated_duration_min: int = Field(default=60, ge=1, le=600)
    estimated_volume: int = Field(default=0, ge=0, le=10_000_000)

    @field_validator("start", "end")
    @classmethod
    def normalize_timezone(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=value.tzinfo or timezone.utc)

    @model_validator(mode="after")
    def validate_time_order(self) -> CalendarEventCreate:
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        return self


class CalendarEventResponse(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    description: str
    location: str
    type: str
    estimated_duration_min: int
    estimated_volume: int
    ai_insights: dict[str, Any]
    source: str


class CalendarSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(min_length=1, repr=False)
    refresh_token: str | None = Field(default=None, repr=False)
    days_ahead: Literal[7, 14, 30] = 7


class CalendarSyncResponse(BaseModel):
    synced_events: list[CalendarEventResponse]
    total_found: int
    workout_events: int
    sync_timestamp: datetime


class WarmupRecommendation(BaseModel):
    name: str
    sets: int | None = None
    reps: int | None = None
    duration_seconds: int | None = None


class ExerciseInsightsResponse(BaseModel):
    exercise_id: str
    exercise_name: str
    generated_at: datetime
    historical_workouts: int
    estimated_1rm_kg: float | None
    next_session: dict[str, float | int | None]
    warm_up: dict[str, Any]
    rationale: str


class FormAnalysisResponse(BaseModel):
    exercise: str
    form_score: float
    range_of_motion: float
    feedback: list[str]
    model: str


class AnalyzedSet(BaseModel):
    set_number: int
    reps: int
    weight_kg: float
    rpe: float | None
    volume_kg_reps: float
    estimated_1rm_kg: float


class AnalyzedExercise(BaseModel):
    exercise_id: str | None
    exercise: str
    exercise_type: str
    muscle_group: str
    total_reps: int
    volume_kg_reps: float
    best_set_1rm_kg: float
    average_rpe: float | None
    sets: list[AnalyzedSet]


class AnalyzedWorkoutSession(BaseModel):
    session_id: str
    started_at: datetime
    mood: int
    energy: int
    sleep_quality: int
    session_volume_kg_reps: float
    total_reps: int
    exercises: list[AnalyzedExercise]


class ExerciseProgressSummary(BaseModel):
    exercise_id: str | None
    exercise: str
    workout_count: int
    latest_date: datetime
    latest_estimated_1rm_kg: float
    best_estimated_1rm_kg: float
    estimated_1rm_change_percent: float | None
    volume_change_percent: float | None
    trend: Literal["improving", "maintaining", "declining", "insufficient_data"]
    recommendation: str


class TrainingAnalysisResponse(BaseModel):
    period_days: int
    generated_at: datetime
    sessions_analyzed: int
    truncated: bool
    total_volume_kg_reps: float
    total_reps: int
    sessions: list[AnalyzedWorkoutSession]
    exercise_progress: list[ExerciseProgressSummary]
    general_recommendations: list[str]