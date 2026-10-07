"""
Google Calendar service.

Auth is handled by `src.core.services.google_auth.get_google_credentials`.
Run `python scripts/authorize_google.py` once to generate credentials/token.json.
"""
from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

import pytz
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import get_settings
from src.core.models.domain import CalendarWorkout, ExerciseType
from src.core.services.google_auth import get_google_credentials

logger = logging.getLogger(__name__)

WORKOUT_KEYWORDS = {
    "cardio": ["cardio", "run", "running", "bike", "cycling", "swim", "swimming", "elliptical", "treadmill", "hiit"],
    "strength": ["gym", "workout", "training", "lift", "lifting", "weights", "squat", "bench", "deadlift",
                 "press", "pull", "push", "row", "curl", "extension", "lunge", "dip"],
    "flexibility": ["yoga", "stretch", "stretching", "mobility", "pilates", "foam roll"],
}


class GoogleCalendarService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._service = None  # lazy-init

    # ── Auth ─────────────────────────────────────────────────────────────────

    def _build_service(self):
        """Build the Calendar API service using the shared credential helper."""
        creds = get_google_credentials()
        logger.info("Calendar: credentials loaded (type=%s)", type(creds).__name__)
        return build("calendar", "v3", credentials=creds)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    # ── Public API ───────────────────────────────────────────────────────────

    async def get_workout_schedule(
        self,
        user_id: str,
        start_date: datetime | None = None,
        days_ahead: int = 7,
    ) -> list[dict]:
        """
        Fetch upcoming calendar events and return only workout-related ones,
        enriched with AI-detected type and insights.
        """
        start = start_date or datetime.now(pytz.UTC)
        end = start + timedelta(days=days_ahead)

        raw_events = await self._fetch_events(start, end)
        workout_events = self._classify_workouts(raw_events)

        for event in workout_events:
            event["ai_insights"] = self._generate_workout_insights(event)

        logger.info(
            "Calendar sync for user=%s: found %d/%d workout events",
            user_id, len(workout_events), len(raw_events),
        )
        return workout_events

    async def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str | None = None,
    ) -> list[dict]:
        """Raw event fetch — useful for custom filtering."""
        return await self._fetch_events(start, end, calendar_id)

    # ── Internal ─────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _fetch_events(
        self,
        start: datetime,
        end: datetime,
        calendar_id: str | None = None,
    ) -> list[dict[str, Any]]:
        loop = asyncio.get_event_loop()
        cal_id = calendar_id or self.settings.google_calendar_id

        def _call():
            try:
                request = self.service.events().list(
                    calendarId=cal_id,
                    timeMin=start.isoformat(),
                    timeMax=end.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=100,
                )
                response = request.execute()
                return response.get("items", [])
            except HttpError as exc:
                logger.error("Calendar API HTTP error: %s", exc)
                raise

        return await loop.run_in_executor(self._executor, _call)

    def _classify_workouts(self, events: list[dict]) -> list[dict]:
        """Filter events to workout-related ones and enrich with metadata."""
        results = []
        for event in events:
            summary = event.get("summary", "").lower()
            description = event.get("description", "").lower()
            combined = f"{summary} {description}"

            detected_type = self._detect_exercise_type(combined)
            if detected_type is None:
                continue  # not a workout event

            results.append({
                "id": event.get("id"),
                "title": event.get("summary", "Workout"),
                "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                "description": event.get("description", ""),
                "location": event.get("location", ""),
                "type": detected_type.value,
                "estimated_duration_min": self._estimate_duration(event),
                "estimated_volume": self._estimate_volume(summary),
            })
        return results

    def _detect_exercise_type(self, text: str) -> ExerciseType | None:
        """Return exercise type if any workout keyword matches, else None."""
        for ex_type, keywords in WORKOUT_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return ExerciseType(ex_type)
        return None

    def _estimate_duration(self, event: dict) -> int:
        """Estimate duration in minutes from event start/end times."""
        try:
            start_str = event.get("start", {}).get("dateTime")
            end_str = event.get("end", {}).get("dateTime")
            if start_str and end_str:
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                return max(0, int((end_dt - start_dt).total_seconds() / 60))
        except (ValueError, TypeError):
            pass
        return 60  # default 60 min

    def _estimate_volume(self, summary: str) -> int:
        """Rough volume estimate from numbers in the event title."""
        numbers = re.findall(r"\d+", summary)
        if numbers:
            return int(numbers[0]) * 10
        return 0

    def _generate_workout_insights(self, event: dict) -> dict:
        """
        Rule-based insight generation.
        Swap this for LLM calls in Phase 4.
        """
        title = event.get("title", "").lower()
        ex_type = event.get("type", "mixed")

        focus_muscles: list[str] = []
        suggested_warmup: list[str] = []

        if "bench" in title or "chest" in title:
            focus_muscles = ["chest", "anterior deltoid", "triceps"]
            suggested_warmup = ["Band pull-aparts x 20", "Shoulder rotations x 10", "Incline DB fly x 12 (light)"]
        elif "squat" in title or "leg" in title:
            focus_muscles = ["quadriceps", "glutes", "hamstrings"]
            suggested_warmup = ["Goblet squats x 10 (light)", "Hip circles x 10", "Leg swings x 10"]
        elif "deadlift" in title or "back" in title:
            focus_muscles = ["hamstrings", "glutes", "erectors", "lats"]
            suggested_warmup = ["Good mornings x 10", "Cat-cow x 10", "Romanian DL x 8 (light)"]
        elif "pull" in title or "row" in title:
            focus_muscles = ["lats", "rhomboids", "biceps"]
            suggested_warmup = ["Dead hangs x 20s", "Scapular pull-ups x 10", "Face pulls x 15"]

        return {
            "focus_muscles": focus_muscles,
            "suggested_warmup": suggested_warmup,
            "warm_up_time_min": 10,
            "estimated_duration_min": event.get("estimated_duration_min", 60),
            "type": ex_type,
        }
