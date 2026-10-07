"""
Workout API routes — Phase 1 full implementation.
/predict and /analyze-form are stubbed here; implemented in Phase 2 & 3.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File, status

from src.api.middleware.auth import get_current_user
from src.core.models.domain import (
    SessionMetadata,
    WorkoutEntry,
    ExerciseType,
    MuscleGroup,
)
from src.core.models.domain import (
    WorkoutLogRequest,
    WorkoutLogResponse,
    ScheduleSyncResponse,
    ProgressResponse,
)
from src.core.services.calendar import GoogleCalendarService
from src.core.services.sheets import GoogleSheetsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workout", tags=["workout"])


# ── Dependency providers ──────────────────────────────────────────────────────

def get_calendar_service() -> GoogleCalendarService:
    return GoogleCalendarService()


def get_sheets_service() -> GoogleSheetsService:
    return GoogleSheetsService()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/log", response_model=WorkoutLogResponse)
async def log_workout(
    payload: WorkoutLogRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[str, Depends(get_current_user)],
    sheets: Annotated[GoogleSheetsService, Depends(get_sheets_service)],
):
    """
    Log a completed workout session.

    Accepts multiple exercises in one call. Returns per-entry insights
    and a total volume figure. Background task queues AI analysis for Phase 2+.
    """
    # Map schema → domain objects
    entries = [
        WorkoutEntry(
            exercise=e.exercise,
            sets=e.sets,
            reps=e.reps,
            weight_kg=e.weight_kg,
            rpe=e.rpe,
            exercise_type=e.exercise_type,
            muscle_group=e.muscle_group,
            notes=e.notes,
            form_score=e.form_score,
            range_of_motion=e.range_of_motion,
            device_data=e.device_data,
        )
        for e in payload.entries
    ]
    metadata = SessionMetadata(
        mood=payload.session_metadata.mood,
        energy=payload.session_metadata.energy,
        sleep_quality=payload.session_metadata.sleep_quality,
        notes=payload.session_metadata.notes,
    )

    try:
        result = await sheets.log_workout(
            user_id=payload.user_id,
            entries=entries,
            metadata=metadata,
        )
    except Exception as exc:
        logger.error("Failed to log workout for user=%s: %s", payload.user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to write to Google Sheets. Check credentials.",
        ) from exc

    # Queue background AI analysis (Phase 2 fills this in)
    background_tasks.add_task(_background_analysis, payload.user_id, entries)

    return WorkoutLogResponse(
        logged_entries=result["logged_entries"],
        total_volume=result["total_volume"],
        insights=result["insights"],
        timestamp=result["timestamp"],
    )


@router.post("/schedule/sync", response_model=ScheduleSyncResponse)
async def sync_schedule(
    current_user: Annotated[str, Depends(get_current_user)],
    calendar: Annotated[GoogleCalendarService, Depends(get_calendar_service)],
    days_ahead: Annotated[int, Query(ge=1, le=30)] = 7,
):
    """
    Sync upcoming workout events from Google Calendar.
    Returns events classified as workouts with AI-generated insights.
    """
    try:
        schedule = await calendar.get_workout_schedule(
            user_id=current_user,
            days_ahead=days_ahead,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.error("Calendar sync failed for user=%s: %s", current_user, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch Google Calendar events.",
        ) from exc

    return ScheduleSyncResponse(
        schedule=schedule,
        total_workouts=len(schedule),
        sync_timestamp=datetime.utcnow().isoformat(),
    )


@router.get("/progress/{exercise}")
async def get_progress(
    exercise: str,
    current_user: Annotated[str, Depends(get_current_user)],
    sheets: Annotated[GoogleSheetsService, Depends(get_sheets_service)],
    days: Annotated[int, Query(ge=7, le=365)] = 90,
):
    """Get performance analytics for a specific exercise."""
    try:
        data = await sheets.get_exercise_progress(current_user, exercise)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])

    return data


@router.get("/history")
async def get_history(
    current_user: Annotated[str, Depends(get_current_user)],
    sheets: Annotated[GoogleSheetsService, Depends(get_sheets_service)],
    exercise: str | None = Query(None),
    days: Annotated[int, Query(ge=1, le=365)] = 30,
):
    """Fetch raw workout history as JSON records."""
    try:
        df = await sheets.get_user_history(current_user, exercise=exercise, days=days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if df.empty:
        return {"records": [], "count": 0}

    # Convert datetimes to string for JSON serialisation
    df["date"] = df["date"].astype(str)
    return {"records": df.to_dict("records"), "count": len(df)}


@router.post("/analyze-form")
async def analyze_form(
    file: UploadFile = File(...),
    exercise_type: str = Query(..., description="squat | bench_press | deadlift | ..."),
    current_user: str = Depends(get_current_user),
):
    """
    [Phase 3 stub] Upload a workout video for form analysis.
    Returns a placeholder until Phase 3 wires in MediaPipe.
    """
    return {
        "status": "stub",
        "message": "Form analysis will be available in Phase 3 (MediaPipe + YOLOv8).",
        "exercise_type": exercise_type,
        "filename": file.filename,
    }


@router.get("/predict/{exercise}")
async def predict_next_workout(
    exercise: str,
    current_user: str = Depends(get_current_user),
):
    """
    [Phase 2 stub] Predict next session's weight/reps/RPE using LSTM.
    Returns a placeholder until Phase 2 wires in the model.
    """
    return {
        "status": "stub",
        "message": "LSTM prediction will be available in Phase 2.",
        "exercise": exercise,
    }


# ── Background tasks ──────────────────────────────────────────────────────────

async def _background_analysis(user_id: str, entries: list[WorkoutEntry]) -> None:
    """
    Placeholder for Phase 2 background AI analysis.
    Runs after the response is already sent to the client.
    """
    await asyncio.sleep(0)  # yield to event loop
    logger.debug(
        "Background analysis queued for user=%s (%d exercises). "
        "Full implementation in Phase 2.",
        user_id, len(entries),
    )
