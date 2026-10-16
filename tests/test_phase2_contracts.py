import asyncio
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.middleware.auth import get_current_user
from src.api.v1.routes import ai as ai_module
from src.api.v1.routes.ai import _build_training_analysis
from src.core.models.phase2_schemas import CalendarEventCreate
from src.data.models.fitness import WorkoutLog, WorkoutSession, WorkoutSet
from src.main import app
from uuid import uuid4


def test_calendar_event_normalizes_naive_timestamps_and_rejects_invalid_range():
    event = CalendarEventCreate(
        title="Strength workout",
        start="2026-10-17T09:00:00",
        end="2026-10-17T10:00:00",
    )

    assert event.start == datetime(2026, 10, 17, 9, tzinfo=timezone.utc)
    assert event.end > event.start

    with pytest.raises(ValidationError):
        CalendarEventCreate(
            title="Invalid workout",
            start="2026-10-17T10:00:00Z",
            end="2026-10-17T09:00:00Z",
        )


def test_phase2_routes_are_mounted():
    routes = {(route.path, method) for route in app.routes for method in getattr(route, "methods", [])}

    assert ("/api/v1/calendar/events", "GET") in routes
    assert ("/api/v1/calendar/events", "POST") in routes
    assert ("/api/v1/calendar/sync", "POST") in routes
    assert ("/api/v1/auth/connections", "GET") in routes
    assert ("/api/v1/ai/insights", "GET") in routes
    assert ("/api/v1/ai/analyze-form", "POST") in routes
    assert ("/api/v1/ai/training-analysis", "GET") in routes


def test_training_analysis_preserves_every_logged_set_and_computes_trend():
    user_id = uuid4()

    def workout(day: int, weight: str, reps: int) -> WorkoutSession:
        entry = WorkoutLog(
            id=day,
            session_id=uuid4(),
            user_id=user_id,
            exercise_id="ex-bench-press",
            exercise="Bench Press",
            exercise_type="strength",
            muscle_group="chest",
            sets_count=2,
            total_reps=reps * 2,
            sets=[
                WorkoutSet(
                    id=uuid4(),
                    log_id=day,
                    user_id=user_id,
                    set_number=set_number,
                    reps=reps,
                    weight_kg=weight,
                    rpe="7.0",
                )
                for set_number in (1, 2)
            ],
        )
        return WorkoutSession(
            id=uuid4(),
            user_id=user_id,
            started_at=datetime(2026, 10, day, tzinfo=timezone.utc),
            mood=8,
            energy=7,
            sleep_quality=8,
            entries=[entry],
        )

    result = _build_training_analysis([workout(16, "75.0", 5), workout(1, "70.0", 5)], 365, False)

    assert result.sessions_analyzed == 2
    assert result.total_reps == 20
    assert len(result.sessions[0].exercises[0].sets) == 2
    assert result.sessions[0].exercises[0].sets[0].volume_kg_reps == 375
    assert result.exercise_progress[0].trend == "improving"
    assert result.exercise_progress[0].estimated_1rm_change_percent == 7.1


def test_local_phone_video_upload_accepts_quicktime(monkeypatch):
    user_id = "c3a2f12d-448f-4a37-9e56-93a34852f2e1"
    previous_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: user_id
    received = {}

    async def fake_analyze(exercise, video_bytes, mime_type, video_url):
        received.update(
            exercise=exercise,
            video_bytes=video_bytes,
            mime_type=mime_type,
            video_url=video_url,
        )
        return 8.5, 92.0, ["Keep a neutral spine."], "gemini-2.5-flash"

    monkeypatch.setattr(ai_module, "_analyze_with_gemini", fake_analyze)
    try:
        response = TestClient(app).post(
            "/api/v1/ai/analyze-form",
            data={"exercise": "Deadlift"},
            files={"video": ("phone-clip.mov", b"video bytes", "video/quicktime")},
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_override

    assert response.status_code == 200
    assert received == {
        "exercise": "Deadlift",
        "video_bytes": b"video bytes",
        "mime_type": "video/mov",
        "video_url": None,
    }


def test_video_upload_enforces_size_limit(monkeypatch):
    user_id = "c3a2f12d-448f-4a37-9e56-93a34852f2e1"
    previous_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: user_id
    monkeypatch.setattr(ai_module, "GEMINI_VIDEO_LIMIT", 4)
    monkeypatch.setattr(
        ai_module,
        "_analyze_with_gemini",
        lambda *args: pytest.fail("oversized upload must be rejected before calling Gemini"),
    )
    try:
        response = TestClient(app).post(
            "/api/v1/ai/analyze-form",
            data={"exercise": "Deadlift"},
            files={"video": ("phone-clip.mp4", b"12345", "video/mp4")},
        )
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_override

    assert response.status_code == 413
    assert "100 MB" in response.json()["detail"]


def test_public_youtube_request_uses_interactions_without_retention(monkeypatch):
    request_data = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "steps": [
                    {"type": "model_output", "content": [{"type": "text", "text": '{"form_score":8,"range_of_motion":90,"feedback":["Stable stance."]}'}]}
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, **kwargs):
            request_data.update(url=url, **kwargs)
            return FakeResponse()

    monkeypatch.setattr(ai_module, "get_settings", lambda: SimpleNamespace(
        gemini_api_key="test-key", gemini_model="gemini-2.5-flash"
    ))
    monkeypatch.setattr(ai_module.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(
        ai_module._analyze_with_gemini(
            "Squat", None, None, "https://www.youtube.com/watch?v=public123"
        )
    )

    assert result == (8.0, 90.0, ["Stable stance."], "gemini-2.5-flash")
    assert request_data["url"].endswith("/interactions")
    assert request_data["json"]["store"] is False
    assert request_data["json"]["input"][0]["uri"] == "https://www.youtube.com/watch?v=public123"


def test_private_youtube_provider_error_suggests_local_upload(monkeypatch):
    class FakeResponse:
        status_code = 403

        def json(self):
            return {"error": {"message": "The YouTube video is private and not publicly accessible."}}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(ai_module, "get_settings", lambda: SimpleNamespace(
        gemini_api_key="test-key", gemini_model="gemini-2.5-flash"
    ))
    monkeypatch.setattr(ai_module.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ai_module._analyze_with_gemini(
                "Squat", None, None, "https://www.youtube.com/watch?v=private123"
            )
        )

    assert error.value.status_code == 422
    assert "upload a local copy" in error.value.detail


def test_gemini_service_unavailable_returns_retryable_503(monkeypatch):
    class FakeResponse:
        status_code = 503
        headers = {"Retry-After": "30"}

        def json(self):
            return {"error": {"message": "Service unavailable. Try again later."}}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(ai_module, "get_settings", lambda: SimpleNamespace(
        gemini_api_key="test-key", gemini_model="gemini-2.5-flash"
    ))
    monkeypatch.setattr(ai_module.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            ai_module._analyze_with_gemini(
                "Squat", None, None, "https://www.youtube.com/watch?v=public123"
            )
        )

    assert error.value.status_code == 503
    assert error.value.headers == {"Retry-After": "30"}
    assert "Retry in about 30 seconds" in error.value.detail