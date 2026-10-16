"""
Domain models and Pydantic v2 schemas.
Keep domain models pure (no ORM), schemas handle API I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class ExerciseType(str, Enum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    FLEXIBILITY = "flexibility"
    MIXED = "mixed"


class MuscleGroup(str, Enum):
    CHEST = "chest"
    BACK = "back"
    LEGS = "legs"
    SHOULDERS = "shoulders"
    ARMS = "arms"
    CORE = "core"
    FULL_BODY = "full_body"


class WorkoutStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


# ─────────────────────────────────────────────────────────────────────────────
# Domain dataclasses (business logic layer — no Pydantic overhead)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WorkoutEntry:
    exercise: str
    sets: int
    reps: int
    weight_kg: float
    rpe: float = 5.0
    exercise_type: ExerciseType = ExerciseType.STRENGTH
    muscle_group: MuscleGroup = MuscleGroup.FULL_BODY
    notes: str = ""
    form_score: float | None = None
    range_of_motion: float | None = None
    device_data: str = ""

    @property
    def volume(self) -> float:
        return self.sets * self.reps * self.weight_kg

    @property
    def estimated_1rm(self) -> float:
        """Epley formula"""
        if self.reps <= 0 or self.weight_kg <= 0:
            return 0.0
        return self.weight_kg * (1 + self.reps / 30)


@dataclass
class SessionMetadata:
    mood: int = 5           # 1-10
    energy: int = 5         # 1-10
    sleep_quality: int = 5  # 1-10
    bodyweight_kg: float | None = None
    notes: str = ""


@dataclass
class WorkoutSession:
    user_id: str
    entries: list[WorkoutEntry]
    metadata: SessionMetadata
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    status: WorkoutStatus = WorkoutStatus.IN_PROGRESS

    @property
    def total_volume(self) -> float:
        return sum(e.volume for e in self.entries)

    @property
    def exercise_count(self) -> int:
        return len(set(e.exercise for e in self.entries))


@dataclass
class CalendarWorkout:
    id: str
    title: str
    start: str
    end: str
    exercise_type: ExerciseType
    description: str = ""
    location: str = ""
    estimated_volume: int = 0
    ai_insights: dict[str, Any] = field(default_factory=dict)


@dataclass
class PersonalRecord:
    exercise: str
    type: str           # "weight_pr" | "volume_pr" | "1rm_pr"
    value: float
    date: str
    reps: int = 0


class ScheduleSyncResponse(BaseModel):
    status: str = "success"
    schedule: list[dict]
    total_workouts: int
    sync_timestamp: str


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    environment: str
    timestamp: str
