from __future__ import annotations

import asyncio
import json
import mimetypes
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.middleware.auth import get_current_user
from src.core.config import get_settings
from src.core.models.phase2_schemas import (
    AnalyzedExercise,
    AnalyzedSet,
    AnalyzedWorkoutSession,
    ExerciseInsightsResponse,
    ExerciseProgressSummary,
    FormAnalysisResponse,
    TrainingAnalysisResponse,
)
from src.data.database import get_db
from src.data.models.fitness import Exercise, WorkoutLog, WorkoutSession

router = APIRouter(prefix="/ai", tags=["ai"])
GEMINI_VIDEO_LIMIT = 100 * 1024 * 1024
GEMINI_API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
SUPPORTED_VIDEO_TYPES = {
    "video/mp4", "video/mpeg", "video/mov", "video/avi", "video/x-flv",
    "video/mpg", "video/webm", "video/wmv", "video/3gpp",
}

WARMUPS = {
    "chest": ["Band pull-aparts", "Shoulder circles", "Incline push-ups"],
    "back": ["Cat-cow", "Scapular pull-ups", "Light rows"],
    "legs": ["Bodyweight squats", "Hip hinges", "Leg swings"],
    "shoulders": ["Arm circles", "Band external rotations", "Light lateral raises"],
    "arms": ["Wrist circles", "Band curls", "Light triceps extensions"],
    "core": ["Dead bugs", "Bird dogs", "Front plank"],
    "full_body": ["Easy cardio", "Dynamic lunges", "Inchworms"],
}


def _user_uuid(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Supabase user ID") from exc


def _one_rm(weight: float, reps: int) -> float:
    return weight * (1 + reps / 30) if 0 < reps <= 30 and weight > 0 else weight


def _percent_change(first: float, last: float) -> float | None:
    if first <= 0:
        return None
    return round((last - first) / first * 100, 1)


def _training_recommendation(
    count: int,
    one_rm_change: float | None,
    latest_average_rpe: float | None,
) -> tuple[str, str]:
    if count < 2 or one_rm_change is None:
        return "insufficient_data", "Log this exercise in at least two sessions to establish a useful trend."
    if latest_average_rpe is not None and latest_average_rpe >= 9:
        return "maintaining", "Recent effort is very high; prioritize recovery and repeat quality reps before adding load."
    if one_rm_change > 2:
        return "improving", "Estimated strength is trending upward. If target reps and technique remain consistent, consider a small load increase next time."
    if one_rm_change < -2:
        return "declining", "Recent estimated strength is lower. Review recovery, sleep, and technique, and avoid forcing a load increase."
    return "maintaining", "Performance is broadly steady. Keep training consistently and change only one progression variable at a time."


def _build_training_analysis(
    workouts: list[WorkoutSession],
    period_days: int,
    truncated: bool,
) -> TrainingAnalysisResponse:
    session_rows: list[AnalyzedWorkoutSession] = []
    progress: dict[tuple[str, str], list[dict[str, Any]]] = {}
    total_volume = 0.0
    total_reps = 0

    for workout in workouts:
        exercise_rows: list[AnalyzedExercise] = []
        session_volume = 0.0
        session_reps = 0
        for entry in workout.entries:
            sets = [
                AnalyzedSet(
                    set_number=item.set_number,
                    reps=item.reps,
                    weight_kg=float(item.weight_kg),
                    rpe=float(item.rpe) if item.rpe is not None else None,
                    volume_kg_reps=float(item.weight_kg) * item.reps,
                    estimated_1rm_kg=round(_one_rm(float(item.weight_kg), item.reps), 2),
                )
                for item in sorted(entry.sets, key=lambda item: item.set_number)
            ]
            entry_volume = sum(item.volume_kg_reps for item in sets)
            entry_reps = sum(item.reps for item in sets)
            valid_rpes = [item.rpe for item in sets if item.rpe is not None]
            best_1rm = max((item.estimated_1rm_kg for item in sets), default=0.0)
            exercise_rows.append(
                AnalyzedExercise(
                    exercise_id=entry.exercise_id,
                    exercise=entry.exercise,
                    exercise_type=entry.exercise_type,
                    muscle_group=entry.muscle_group,
                    total_reps=entry_reps,
                    volume_kg_reps=round(entry_volume, 2),
                    best_set_1rm_kg=round(best_1rm, 2),
                    average_rpe=round(sum(valid_rpes) / len(valid_rpes), 1) if valid_rpes else None,
                    sets=sets,
                )
            )
            session_volume += entry_volume
            session_reps += entry_reps
            key = (entry.exercise_id or "", entry.exercise.casefold())
            progress.setdefault(key, []).append(
                {
                    "date": workout.started_at,
                    "one_rm": best_1rm,
                    "volume": entry_volume,
                    "average_rpe": sum(valid_rpes) / len(valid_rpes) if valid_rpes else None,
                    "exercise_id": entry.exercise_id,
                    "exercise": entry.exercise,
                }
            )
        total_volume += session_volume
        total_reps += session_reps
        session_rows.append(
            AnalyzedWorkoutSession(
                session_id=str(workout.id),
                started_at=workout.started_at,
                mood=workout.mood,
                energy=workout.energy,
                sleep_quality=workout.sleep_quality,
                session_volume_kg_reps=round(session_volume, 2),
                total_reps=session_reps,
                exercises=exercise_rows,
            )
        )

    progress_rows: list[ExerciseProgressSummary] = []
    for samples in progress.values():
        samples.sort(key=lambda item: item["date"])
        first = samples[0]
        latest = samples[-1]
        one_rm_change = _percent_change(first["one_rm"], latest["one_rm"])
        volume_change = _percent_change(first["volume"], latest["volume"])
        trend, recommendation = _training_recommendation(
            len(samples), one_rm_change, latest["average_rpe"]
        )
        progress_rows.append(
            ExerciseProgressSummary(
                exercise_id=latest["exercise_id"],
                exercise=latest["exercise"],
                workout_count=len(samples),
                latest_date=latest["date"],
                latest_estimated_1rm_kg=round(latest["one_rm"], 2),
                best_estimated_1rm_kg=round(max(item["one_rm"] for item in samples), 2),
                estimated_1rm_change_percent=one_rm_change,
                volume_change_percent=volume_change,
                trend=trend,
                recommendation=recommendation,
            )
        )
    progress_rows.sort(key=lambda item: item.exercise.casefold())

    general_recommendations = [
        "Use the same exercise variation and comparable range of motion when comparing strength estimates.",
        "Progress gradually: change load, reps, or sets one at a time, and keep technique consistent.",
    ]
    if truncated:
        general_recommendations.insert(0, "Analysis reached the session limit; narrow the date range for complete detail.")
    if len(workouts) < 3:
        general_recommendations.append("Log more sessions to make trend estimates more reliable.")

    return TrainingAnalysisResponse(
        period_days=period_days,
        generated_at=datetime.now(timezone.utc),
        sessions_analyzed=len(workouts),
        truncated=truncated,
        total_volume_kg_reps=round(total_volume, 2),
        total_reps=total_reps,
        sessions=session_rows,
        exercise_progress=progress_rows,
        general_recommendations=general_recommendations,
    )


@router.get("/training-analysis", response_model=TrainingAnalysisResponse)
async def get_training_analysis(
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: Annotated[int, Query(ge=7, le=3650)] = 365,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> TrainingAnalysisResponse:
    """Analyze workout progression from owned sessions down to each logged set."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(WorkoutSession)
        .options(selectinload(WorkoutSession.entries).selectinload(WorkoutLog.sets))
        .where(
            WorkoutSession.user_id == _user_uuid(current_user),
            WorkoutSession.started_at >= cutoff,
        )
        .order_by(WorkoutSession.started_at.desc())
        .limit(limit + 1)
    )
    workouts = list(result.scalars().unique().all())
    truncated = len(workouts) > limit
    return _build_training_analysis(workouts[:limit], days, truncated)


@router.get("/insights", response_model=ExerciseInsightsResponse)
async def get_exercise_insights(
    exercise: str,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExerciseInsightsResponse:
    """Return warm-up guidance and a transparent estimate based on owned history."""
    user_id = _user_uuid(current_user)
    exercise_result = await db.execute(
        select(Exercise).where(
            Exercise.id == exercise,
            or_(Exercise.user_id.is_(None), Exercise.user_id == user_id),
        )
    )
    exercise_record = exercise_result.scalar_one_or_none()
    if exercise_record is None:
        raise HTTPException(status_code=404, detail="Exercise not found")

    history_result = await db.execute(
        select(WorkoutLog)
        .options(selectinload(WorkoutLog.sets), selectinload(WorkoutLog.session))
        .where(
            WorkoutLog.user_id == user_id,
            or_(
                WorkoutLog.exercise_id == exercise_record.id,
                func.lower(WorkoutLog.exercise) == exercise_record.name.casefold(),
            ),
        )
        .order_by(WorkoutLog.created_at.desc())
        .limit(100)
    )
    entries = list(history_result.scalars().unique().all())
    estimates = [
        max((_one_rm(float(item.weight_kg), item.reps) for item in entry.sets), default=0.0)
        for entry in entries
    ]
    estimates = [value for value in estimates if value > 0]
    current_estimate = estimates[0] if estimates else None
    projected_estimate = current_estimate
    if len(estimates) >= 3:
        chronological = list(reversed(estimates[:6]))
        slope = (chronological[-1] - chronological[0]) / max(len(chronological) - 1, 1)
        projected_estimate = max(0.0, current_estimate + max(-2.5, min(2.5, slope)))

    target_weight = (
        round((projected_estimate * 0.8) / 2.5) * 2.5
        if projected_estimate is not None
        else float(exercise_record.default_weight_kg)
    )
    target_volume = sum(
        sum(float(item.weight_kg) * item.reps for item in entry.sets)
        for entry in entries[:3]
    )
    muscle_group = exercise_record.muscle_group.casefold()
    drills = WARMUPS.get(muscle_group, WARMUPS["full_body"])
    return ExerciseInsightsResponse(
        exercise_id=exercise_record.id,
        exercise_name=exercise_record.name,
        generated_at=datetime.now(timezone.utc),
        historical_workouts=len(entries),
        estimated_1rm_kg=round(current_estimate, 1) if current_estimate is not None else None,
        next_session={
            "target_weight_kg": round(target_weight, 1),
            "target_reps": 5 if current_estimate is not None else exercise_record.default_reps,
            "target_sets": 3 if entries else exercise_record.default_sets,
            "projected_1rm_kg": round(projected_estimate, 1) if projected_estimate is not None else None,
        },
        warm_up={
            "duration_min": 10,
            "focus_muscles": [muscle_group],
            "exercises": [
                {"name": name, "sets": 2, "reps": 10}
                for name in drills
            ],
        },
        rationale=(
            f"Based on {len(entries)} logged workout entries and the last three entries' "
            f"combined volume of {round(target_volume, 1)} kg-reps. Strength estimates use the Epley formula; "
            "the next-session target is a conservative rule-based estimate, not a trained model prediction."
        ),
    )


def _youtube_video_uri(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")):
        raise HTTPException(status_code=422, detail="Video URLs must be public YouTube links; otherwise upload the video")
    return value


def _video_mime_type(upload: UploadFile) -> str:
    mime_type = (upload.content_type or "").lower()
    if mime_type in {"application/octet-stream", "binary/octet-stream", ""}:
        mime_type = mimetypes.guess_type(upload.filename or "")[0] or mime_type
    if mime_type == "video/quicktime":
        mime_type = "video/mov"
    if mime_type not in SUPPORTED_VIDEO_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported video format; upload MP4, MOV, WebM, or another supported video",
        )
    return mime_type


async def _analyze_with_gemini(
    exercise: str,
    video_bytes: bytes | None,
    mime_type: str | None,
    video_url: str | None,
) -> tuple[float, float, list[str], str]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Form analysis model is not configured")

    prompt = (
        "Analyze the uploaded exercise video for movement quality. Return only JSON with keys "
        '"form_score" (number 0-10), "range_of_motion" (number 0-100), and "feedback" '
        "(array of concise observations). Do not infer injury or diagnose. If the movement is not "
        "visible enough, state that in feedback and use conservative scores. Exercise: " + exercise
    )
    input_items: list[dict[str, Any]]
    uploaded_file_name: str | None = None
    if video_bytes is not None:
        video_uri, uploaded_file_name = await _upload_gemini_video(video_bytes, mime_type or "video/mp4")
        input_items = [{"type": "video", "uri": video_uri, "mime_type": mime_type or "video/mp4"}]
    else:
        input_items = [{"type": "video", "uri": _youtube_video_uri(video_url or "")}]
    input_items.append({"type": "text", "text": prompt})
    payload = {"model": settings.gemini_model, "input": input_items, "store": False}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{GEMINI_API_ROOT}/interactions",
                headers={"x-goog-api-key": settings.gemini_api_key},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Form analysis provider is unavailable") from exc
    finally:
        if uploaded_file_name:
            await _delete_gemini_file(uploaded_file_name)
    if response.status_code >= 400:
        try:
            provider_detail = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            provider_detail = ""
        lower_detail = provider_detail.casefold()
        if video_url and response.status_code in {400, 403, 404} and any(
            phrase in lower_detail
            for phrase in ("youtube", "private video", "not public", "not publicly accessible", "video url")
        ):
            raise HTTPException(
                status_code=422,
                detail="Gemini could not access this YouTube video. It must be public; upload a local copy for private or unlisted videos.",
            )
        useful_detail = provider_detail[:300] if provider_detail else "No provider detail was returned."
        if response.status_code in {429, 503}:
            retry_after = response.headers.get("Retry-After")
            detail = "Gemini is temporarily unavailable or rate limited. Please retry shortly."
            if retry_after and retry_after.isdigit():
                detail = f"Gemini is temporarily unavailable or rate limited. Retry in about {retry_after} seconds."
            if provider_detail:
                detail = f"{detail} Provider message: {useful_detail}"
            raise HTTPException(
                status_code=503,
                detail=detail,
                headers={"Retry-After": retry_after} if retry_after else None,
            )
        raise HTTPException(
            status_code=502,
            detail=f"Gemini rejected the video request (HTTP {response.status_code}): {useful_detail}",
        )
    try:
        response_data = response.json()
        text = response_data.get("output_text")
        if not text:
            response_steps = response_data.get("steps", response_data.get("output", []))
            text = next(
                part["text"]
                for step in response_steps
                if step.get("type") == "model_output"
                for part in step.get("content", [])
                if part.get("type") == "text"
            )
        result = json.loads(text)
        score = max(0.0, min(10.0, float(result["form_score"])))
        range_of_motion = max(0.0, min(100.0, float(result["range_of_motion"])))
        feedback = [str(item)[:500] for item in result["feedback"][:10]]
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Form analysis provider returned an invalid result") from exc
    return score, range_of_motion, feedback, settings.gemini_model


async def _upload_gemini_video(video_bytes: bytes, mime_type: str) -> tuple[str, str]:
    settings = get_settings()
    api_key = settings.gemini_api_key
    upload_headers = {
        "x-goog-api-key": api_key,
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(video_bytes)),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            started = await client.post(
                f"https://generativelanguage.googleapis.com/upload/v1beta/files",
                headers=upload_headers,
                json={"file": {"display_name": "fitness-form-analysis"}},
            )
            if started.status_code >= 400:
                raise _gemini_upload_error(started)
            upload_url = started.headers.get("x-goog-upload-url")
            if not upload_url:
                raise HTTPException(status_code=502, detail="Gemini did not return a video upload URL")
            uploaded = await client.post(
                upload_url,
                headers={
                    "Content-Length": str(len(video_bytes)),
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Command": "upload, finalize",
                },
                content=video_bytes,
            )
            if uploaded.status_code >= 400:
                raise _gemini_upload_error(uploaded)
            file_data = uploaded.json().get("file", uploaded.json())
            file_name = file_data.get("name")
            file_uri = file_data.get("uri")
            if not file_name or not file_uri:
                raise HTTPException(status_code=502, detail="Gemini returned incomplete video file metadata")

            for _ in range(30):
                state = file_data.get("state")
                if state == "ACTIVE":
                    return file_uri, file_name
                if state == "FAILED":
                    await _delete_gemini_file(file_name, client)
                    raise HTTPException(status_code=502, detail="Gemini could not process the uploaded video")
                await asyncio.sleep(2)
                file_response = await client.get(
                    f"{GEMINI_API_ROOT}/{file_name}",
                    headers={"x-goog-api-key": api_key},
                )
                if file_response.status_code >= 400:
                    raise _gemini_upload_error(file_response)
                file_data = file_response.json()
            await _delete_gemini_file(file_name, client)
            raise HTTPException(status_code=504, detail="Gemini video processing timed out; try a shorter clip")
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Video upload to Gemini failed") from exc


def _gemini_upload_error(response: httpx.Response) -> HTTPException:
    try:
        detail = response.json().get("error", {}).get("message", "")
    except (ValueError, AttributeError):
        detail = ""
    retry_after = response.headers.get("Retry-After")
    if response.status_code in {429, 503}:
        message = "Gemini video upload is temporarily unavailable or rate limited. Please retry shortly."
        if retry_after and retry_after.isdigit():
            message = f"Gemini video upload is temporarily unavailable or rate limited. Retry in about {retry_after} seconds."
        if detail:
            message = f"{message} Provider message: {detail[:300]}"
        return HTTPException(
            status_code=503,
            detail=message,
            headers={"Retry-After": retry_after} if retry_after else None,
        )
    return HTTPException(
        status_code=502,
        detail=f"Gemini video upload failed (HTTP {response.status_code}): {detail[:300] or 'No provider detail was returned.'}",
    )


async def _delete_gemini_file(file_name: str, client: httpx.AsyncClient | None = None) -> None:
    settings = get_settings()
    try:
        if client is not None:
            await client.delete(
                f"{GEMINI_API_ROOT}/{file_name}",
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
        else:
            async with httpx.AsyncClient(timeout=10.0) as cleanup_client:
                await cleanup_client.delete(
                    f"{GEMINI_API_ROOT}/{file_name}",
                    headers={"x-goog-api-key": settings.gemini_api_key},
                )
    except httpx.HTTPError:
        return


@router.post("/analyze-form", response_model=FormAnalysisResponse)
async def analyze_form(
    current_user: Annotated[str, Depends(get_current_user)],
    exercise: Annotated[str, Form(min_length=1, max_length=100)],
    video: Annotated[UploadFile | None, File()] = None,
    video_url: Annotated[str | None, Form()] = None,
) -> FormAnalysisResponse:
    """Analyze an uploaded clip or a public YouTube URL without retaining the video."""
    del current_user  # Authentication is required even though the model call is stateless.
    if bool(video) == bool(video_url):
        raise HTTPException(status_code=422, detail="Provide exactly one of video or video_url")

    video_bytes = None
    mime_type = None
    if video is not None:
        mime_type = _video_mime_type(video)
        video_bytes = await video.read(GEMINI_VIDEO_LIMIT + 1)
        if len(video_bytes) > GEMINI_VIDEO_LIMIT:
            raise HTTPException(status_code=413, detail="Video exceeds the 100 MB upload limit")
    else:
        _youtube_video_uri(video_url or "")

    score, range_of_motion, feedback, model = await _analyze_with_gemini(
        exercise.strip(), video_bytes, mime_type, video_url
    )
    return FormAnalysisResponse(
        exercise=exercise.strip(),
        form_score=round(score, 2),
        range_of_motion=round(range_of_motion, 2),
        feedback=feedback,
        model=model,
    )