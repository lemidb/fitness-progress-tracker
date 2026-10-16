from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import get_current_user
from src.core.models.domain import ExerciseType, MuscleGroup
from src.core.models.workout_schemas import ExerciseCreateRequest, ExerciseResponse
from src.data.database import get_db
from src.data.models.fitness import Exercise

router = APIRouter(prefix="/exercises", tags=["exercises"])


def _serialize(exercise: Exercise) -> ExerciseResponse:
    return ExerciseResponse(
        id=exercise.id,
        name=exercise.name,
        muscle_group=exercise.muscle_group,
        exercise_type=exercise.exercise_type,
        default_weight_kg=float(exercise.default_weight_kg),
        default_sets=exercise.default_sets,
        default_reps=exercise.default_reps,
    )


@router.get("", response_model=list[ExerciseResponse])
async def list_exercises(
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None, min_length=1, max_length=100),
    muscle_group: MuscleGroup | None = None,
    exercise_type: ExerciseType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ExerciseResponse]:
    """Search the shared exercise catalog for authenticated users."""
    query = select(Exercise)
    owner_id = uuid.UUID(current_user)
    query = query.where(or_(Exercise.user_id.is_(None), Exercise.user_id == owner_id))
    if search:
        query = query.where(func.lower(Exercise.name).contains(search.strip().lower()))
    if muscle_group:
        query = query.where(Exercise.muscle_group == muscle_group.value)
    if exercise_type:
        query = query.where(Exercise.exercise_type == exercise_type.value)
    result = await db.execute(query.order_by(Exercise.name).limit(limit))
    return [_serialize(item) for item in result.scalars().all()]


@router.post("", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
async def create_exercise(
    payload: ExerciseCreateRequest,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseResponse:
    """Create a private exercise visible only to its owner."""
    owner_id = uuid.UUID(current_user)
    existing = await db.execute(
        select(Exercise.id).where(
            Exercise.user_id == owner_id,
            func.lower(Exercise.name) == payload.name.lower(),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="You already have an exercise with this name")

    exercise = Exercise(
        id=f"custom-{uuid.uuid4()}",
        name=payload.name,
        muscle_group=payload.muscle_group.value,
        exercise_type=payload.exercise_type.value,
        default_weight_kg=payload.default_weight_kg,
        default_sets=payload.default_sets,
        default_reps=payload.default_reps,
        user_id=owner_id,
    )
    db.add(exercise)
    await db.commit()
    await db.refresh(exercise)
    return _serialize(exercise)


@router.get("/{exercise_id}", response_model=ExerciseResponse)
async def get_exercise(
    exercise_id: str,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseResponse:
    owner_id = uuid.UUID(current_user)
    result = await db.execute(
        select(Exercise).where(
            Exercise.id == exercise_id,
            or_(Exercise.user_id.is_(None), Exercise.user_id == owner_id),
        )
    )
    exercise = result.scalar_one_or_none()
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return _serialize(exercise)


@router.delete("/{exercise_id}")
async def delete_exercise(
    exercise_id: str,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete only a caller-owned custom exercise; shared catalog rows are immutable."""
    owner_id = uuid.UUID(current_user)
    result = await db.execute(
        select(Exercise).where(
            Exercise.id == exercise_id,
            Exercise.user_id == owner_id,
        )
    )
    exercise = result.scalar_one_or_none()
    if exercise is None:
        raise HTTPException(status_code=404, detail="Custom exercise not found")
    await db.delete(exercise)
    await db.commit()
    return {"status": "deleted"}
