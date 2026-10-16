from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.middleware.auth import get_current_user
from src.core.models.workout_schemas import WorkoutLogRequest, WorkoutLogResponse
from src.data.database import get_db
from src.data.models.fitness import Exercise, WorkoutLog, WorkoutSession, WorkoutSet

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workout", tags=["workout"])


def _user_uuid(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Supabase user ID") from exc


def _session_query():
    return selectinload(WorkoutSession.entries).selectinload(WorkoutLog.sets)


def _entry_stats(entry: WorkoutLog) -> dict[str, float]:
    volume = sum(float(item.weight_kg) * item.reps for item in entry.sets)
    max_weight = max((float(item.weight_kg) for item in entry.sets), default=0.0)
    max_one_rm = max(
        (
            float(item.weight_kg) * (1 + item.reps / 30)
            if item.reps > 0
            else float(item.weight_kg)
            for item in entry.sets
        ),
        default=0.0,
    )
    return {"volume": volume, "max_weight": max_weight, "one_rm": max_one_rm}


def _serialize_session(workout: WorkoutSession) -> dict[str, Any]:
    serialized_entries = []
    session_volume = 0.0
    for entry in workout.entries:
        stats = _entry_stats(entry)
        session_volume += stats["volume"]
        serialized_entries.append(
            {
                "id": entry.id,
                "exercise_id": entry.exercise_id,
                "exercise": entry.exercise,
                "exercise_type": entry.exercise_type,
                "muscle_group": entry.muscle_group,
                "sets_count": entry.sets_count,
                "total_reps": entry.total_reps,
                "rpe": float(entry.rpe) if entry.rpe is not None else None,
                "notes": entry.notes,
                "form_score": float(entry.form_score) if entry.form_score is not None else None,
                "range_of_motion": float(entry.range_of_motion) if entry.range_of_motion is not None else None,
                "volume": stats["volume"],
                "estimated_1rm": stats["one_rm"],
                "sets": [
                    {
                        "id": str(workout_set.id),
                        "set_number": workout_set.set_number,
                        "reps": workout_set.reps,
                        "weight_kg": float(workout_set.weight_kg),
                        "rpe": float(workout_set.rpe) if workout_set.rpe is not None else None,
                    }
                    for workout_set in entry.sets
                ],
            }
        )
    return {
        "id": str(workout.id),
        "started_at": workout.started_at.isoformat(),
        "completed_at": workout.completed_at.isoformat() if workout.completed_at else None,
        "mood": workout.mood,
        "energy": workout.energy,
        "sleep_quality": workout.sleep_quality,
        "bodyweight_kg": float(workout.bodyweight_kg) if workout.bodyweight_kg is not None else None,
        "notes": workout.notes,
        "exercise_count": len(serialized_entries),
        "total_volume": session_volume,
        "entries": serialized_entries,
    }


@router.post("/log", response_model=WorkoutLogResponse, status_code=status.HTTP_201_CREATED)
async def log_workout(
    payload: WorkoutLogRequest,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkoutLogResponse:
    """Save a single exercise or a multi-exercise session atomically."""
    user_id = _user_uuid(current_user)
    exercise_ids = {entry.exercise_id for entry in payload.entries if entry.exercise_id}
    if exercise_ids:
        result = await db.execute(
            select(Exercise.id).where(
                Exercise.id.in_(exercise_ids),
                or_(Exercise.user_id.is_(None), Exercise.user_id == user_id),
            )
        )
        found_ids = set(result.scalars().all())
        if found_ids != exercise_ids:
            raise HTTPException(status_code=404, detail="One or more exercises were not found")

    exercise_names = {entry.exercise.casefold() for entry in payload.entries}
    previous_result = await db.execute(
        select(WorkoutLog)
        .join(WorkoutSession, WorkoutSession.id == WorkoutLog.session_id)
        .options(selectinload(WorkoutLog.sets))
        .where(
            WorkoutSession.user_id == user_id,
            func.lower(WorkoutLog.exercise).in_(exercise_names),
        )
    )
    previous_max: dict[str, float] = {}
    for previous_entry in previous_result.scalars().unique():
        key = previous_entry.exercise.casefold()
        previous_max[key] = max(
            previous_max.get(key, 0.0),
            max((float(item.weight_kg) for item in previous_entry.sets), default=0.0),
        )

    metadata = payload.session_metadata
    started_at = payload.started_at or datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    workout = WorkoutSession(
        user_id=user_id,
        started_at=started_at,
        completed_at=datetime.now(timezone.utc),
        mood=metadata.mood,
        energy=metadata.energy,
        sleep_quality=metadata.sleep_quality,
        bodyweight_kg=metadata.bodyweight_kg,
        notes=metadata.notes,
        entries=[],
    )

    insights = []
    total_volume = 0.0
    for entry_input in payload.entries:
        reps_total = sum(item.reps for item in entry_input.sets)
        entry = WorkoutLog(
            user_id=user_id,
            exercise_id=entry_input.exercise_id,
            exercise=entry_input.exercise,
            exercise_type=entry_input.exercise_type.value,
            muscle_group=entry_input.muscle_group.value,
            sets_count=len(entry_input.sets),
            total_reps=reps_total,
            rpe=entry_input.rpe,
            notes=entry_input.notes,
            form_score=entry_input.form_score,
            range_of_motion=entry_input.range_of_motion,
            device_data=entry_input.device_data,
            sets=[
                WorkoutSet(
                    user_id=user_id,
                    set_number=set_number,
                    reps=workout_set.reps,
                    weight_kg=workout_set.weight_kg,
                    rpe=workout_set.rpe,
                )
                for set_number, workout_set in enumerate(entry_input.sets, start=1)
            ],
        )
        workout.entries.append(entry)
        current_max = max((item.weight_kg for item in entry_input.sets), default=0.0)
        old_max = previous_max.get(entry_input.exercise.casefold(), 0.0)
        total_volume += sum(item.reps * item.weight_kg for item in entry_input.sets)
        form_quality = (
            "not_recorded"
            if entry_input.form_score is None
            else "good"
            if entry_input.form_score >= 7
            else "needs_improvement"
        )
        insights.append(
            {
                "exercise": entry_input.exercise,
                "is_pr": current_max > old_max,
                "prev_max_kg": old_max,
                "form_quality": form_quality,
                "suggestion": (
                    "New weight personal record."
                    if current_max > old_max
                    else "Keep building consistent quality sets."
                ),
            }
        )

    db.add(workout)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Workout transaction failed for user=%s", current_user)
        raise HTTPException(status_code=503, detail="Workout could not be saved")

    return WorkoutLogResponse(
        session_id=str(workout.id),
        logged_entries=len(workout.entries),
        total_volume=total_volume,
        insights=insights,
        timestamp=workout.started_at.isoformat(),
    )


@router.get("/history")
async def get_history(
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    exercise: str | None = Query(None, min_length=1, max_length=100),
    muscle_group: str | None = Query(None, max_length=32),
    days: Annotated[int, Query(ge=1, le=3650)] = 90,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return this user's workout sessions with individually tracked sets."""
    user_id = _user_uuid(current_user)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = select(WorkoutSession).options(_session_query()).where(
        WorkoutSession.user_id == user_id,
        WorkoutSession.started_at >= cutoff,
    )
    if exercise:
        query = query.where(
            WorkoutSession.entries.any(WorkoutLog.exercise.ilike(f"%{exercise.strip()}%"))
        )
    if muscle_group:
        query = query.where(
            WorkoutSession.entries.any(func.lower(WorkoutLog.muscle_group) == muscle_group.lower())
        )
    query = query.order_by(WorkoutSession.started_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    workouts = result.scalars().unique().all()
    records = [_serialize_session(workout) for workout in workouts]
    return {"records": records, "count": len(records), "limit": limit, "offset": offset}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: uuid.UUID,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(WorkoutSession).where(
            WorkoutSession.id == session_id,
            WorkoutSession.user_id == _user_uuid(current_user),
        )
    )
    workout = result.scalar_one_or_none()
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout session not found")
    await db.delete(workout)
    await db.commit()
    return {"status": "deleted"}


@router.delete("/entries/{entry_id}")
async def delete_workout_entry(
    entry_id: int,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete one owned exercise entry and its sets, preserving the rest of the session."""
    user_id = _user_uuid(current_user)
    result = await db.execute(
        select(WorkoutLog)
        .options(selectinload(WorkoutLog.session).selectinload(WorkoutSession.entries))
        .where(WorkoutLog.id == entry_id, WorkoutLog.user_id == user_id)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Workout entry not found")

    session = entry.session
    if len(session.entries) == 1:
        await db.delete(session)
    else:
        await db.delete(entry)
    await db.commit()
    return {"status": "deleted"}


@router.get("/progress/{exercise}")
async def get_progress(
    exercise: str,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=7, le=3650)] = 365,
):
    """Calculate progress and personal records from the user's per-set data."""
    user_id = _user_uuid(current_user)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(WorkoutLog)
        .join(WorkoutSession, WorkoutSession.id == WorkoutLog.session_id)
        .options(selectinload(WorkoutLog.sets), selectinload(WorkoutLog.session))
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= cutoff,
            func.lower(WorkoutLog.exercise) == exercise.strip().lower(),
        )
        .order_by(WorkoutSession.started_at.asc())
    )
    entries = result.scalars().unique().all()
    if not entries:
        raise HTTPException(status_code=404, detail="No workout history found for this exercise")

    points = []
    for entry in entries:
        stats = _entry_stats(entry)
        points.append(
            {
                "date": entry.session.started_at.isoformat(),
                "max_weight": stats["max_weight"],
                "volume": stats["volume"],
                "one_rm": stats["one_rm"],
            }
        )
    weights = [point["max_weight"] for point in points]
    volumes = [point["volume"] for point in points]
    one_rms = [point["one_rm"] for point in points]
    if len(points) < 3:
        trend = {"direction": "insufficient_data", "slope": 0.0, "projected_weight": None}
    else:
        slope, intercept = np.polyfit(np.arange(len(weights)), np.asarray(weights), 1)
        direction = "improving" if slope > 0.05 else "declining" if slope < -0.05 else "maintaining"
        trend = {
            "direction": direction,
            "slope": round(float(slope), 3),
            "projected_weight": round(float(intercept + slope * (len(weights) + 6)), 2),
        }

    prs = [
        {"type": "weight_pr", "value": max(weights), "date": points[weights.index(max(weights))]["date"]},
        {"type": "volume_pr", "value": max(volumes), "date": points[volumes.index(max(volumes))]["date"]},
        {"type": "1rm_pr", "value": max(one_rms), "date": points[one_rms.index(max(one_rms))]["date"]},
    ]
    return {
        "exercise": entries[0].exercise,
        "date_range": {"start": points[0]["date"], "end": points[-1]["date"]},
        "total_workouts": len(entries),
        "max_weight": max(weights),
        "avg_weight": sum(weights) / len(weights),
        "max_volume": max(volumes),
        "avg_volume": sum(volumes) / len(volumes),
        "trend": trend,
        "prs": prs,
        "points": points,
    }
