from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated, Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import get_current_user
from src.core.config import get_settings
from src.core.models.phase2_schemas import (
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarSyncRequest,
    CalendarSyncResponse,
)
from src.core.services.calendar import GoogleCalendarService
from src.data.database import get_db
from src.data.models.fitness import CalendarEvent, GoogleCalendarConnection

router = APIRouter(prefix="/calendar", tags=["calendar"])
GOOGLE_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _user_uuid(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid Supabase user ID") from exc


def _response(event: CalendarEvent) -> CalendarEventResponse:
    return CalendarEventResponse(
        id=str(event.id),
        title=event.title,
        start=event.start_time,
        end=event.end_time,
        description=event.description,
        location=event.location,
        type=event.exercise_type,
        estimated_duration_min=event.estimated_duration_min,
        estimated_volume=event.estimated_volume,
        ai_insights=event.ai_insights,
        source=event.source,
    )


def _event_time(event: dict[str, Any], key: str) -> datetime | None:
    value = event.get(key, {})
    raw = value.get("dateTime")
    if raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raw_date = value.get("date")
    if raw_date:
        return datetime.combine(date.fromisoformat(raw_date), time.min, tzinfo=timezone.utc)
    return None


async def _refresh_access_token(client: httpx.AsyncClient, refresh_token: str) -> str:
    settings = get_settings()
    if not settings.google_oauth_client_id:
        raise HTTPException(status_code=401, detail="Google access token expired; reconnect Google Calendar")

    form = {
        "client_id": settings.google_oauth_client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    if settings.google_oauth_client_secret:
        form["client_secret"] = settings.google_oauth_client_secret
    try:
        response = await client.post(GOOGLE_TOKEN_URL, data=form)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google token refresh failed") from exc
    if response.status_code != 200 or not response.json().get("access_token"):
        raise HTTPException(status_code=401, detail="Google Calendar authorization expired; reconnect")
    return str(response.json()["access_token"])


async def _get_google_events(
    client: httpx.AsyncClient,
    access_token: str,
    days_ahead: int,
    refresh_token: str | None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    calendar_id = quote(settings.google_calendar_id or "primary", safe="")
    url = GOOGLE_EVENTS_URL.format(calendar_id=calendar_id)
    start = datetime.now(timezone.utc)
    params: dict[str, str | int] = {
        "timeMin": start.isoformat(),
        "timeMax": (start + timedelta(days=days_ahead)).isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 250,
    }
    events: list[dict[str, Any]] = []
    retried_with_refresh = False
    while True:
        try:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail="Google Calendar API is unavailable") from exc
        if response.status_code == 401 and refresh_token and not retried_with_refresh:
            access_token = await _refresh_access_token(client, refresh_token)
            retried_with_refresh = True
            continue
        if response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Google Calendar is not authorized; reconnect")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="Google Calendar could not return events")
        payload = response.json()
        events.extend(payload.get("items", []))
        next_page = payload.get("nextPageToken")
        if not next_page:
            break
        params["pageToken"] = next_page
    return events


@router.get("/events", response_model=list[CalendarEventResponse])
async def get_events(
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    days_ahead: Annotated[int, Query()] = 7,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
) -> list[CalendarEventResponse]:
    """List only the current user's scheduled events in a bounded time range."""
    if days_ahead not in {7, 14, 30}:
        raise HTTPException(status_code=422, detail="days_ahead must be 7, 14, or 30")
    start = start_at or datetime.now(timezone.utc)
    end = end_at or start + timedelta(days=days_ahead)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if end <= start:
        raise HTTPException(status_code=422, detail="end_at must be later than start_at")

    result = await db.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == _user_uuid(current_user),
            CalendarEvent.start_time < end,
            CalendarEvent.end_time >= start,
        )
        .order_by(CalendarEvent.start_time.asc())
    )
    return [_response(event) for event in result.scalars().all()]


@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: CalendarEventCreate,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalendarEventResponse:
    """Create a manually scheduled event owned by the authenticated user."""
    event = CalendarEvent(
        user_id=_user_uuid(current_user),
        title=payload.title.strip(),
        start_time=payload.start,
        end_time=payload.end,
        description=payload.description,
        location=payload.location,
        exercise_type=payload.type,
        estimated_duration_min=payload.estimated_duration_min,
        estimated_volume=payload.estimated_volume,
        ai_insights={},
        source="manual",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return _response(event)


@router.post("/sync", response_model=CalendarSyncResponse)
async def sync_calendar(
    payload: CalendarSyncRequest,
    current_user: Annotated[str, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalendarSyncResponse:
    """Import workout events using the caller's short-lived Google OAuth tokens."""
    user_id = _user_uuid(current_user)
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            raw_events = await _get_google_events(
                client, payload.access_token, payload.days_ahead, payload.refresh_token
            )
    except HTTPException as exc:
        if exc.status_code == 401:
            connection_result = await db.execute(
                select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user_id)
            )
            connection = connection_result.scalar_one_or_none()
            if connection is not None:
                connection.is_connected = False
                await db.commit()
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google Calendar connection could not be verified") from exc

    calendar_service = GoogleCalendarService()
    workout_events = calendar_service._classify_workouts(raw_events)
    for item in workout_events:
        item["ai_insights"] = calendar_service._generate_workout_insights(item)

    provider_ids = [item["id"] for item in workout_events if item.get("id")]
    existing_result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.provider_event_id.in_(provider_ids),
        )
    ) if provider_ids else None
    existing = {
        event.provider_event_id: event
        for event in existing_result.scalars().all()
    } if existing_result is not None else {}
    synced: list[CalendarEvent] = []
    for item in workout_events:
        event_id = item.get("id")
        start = _event_time({"start": {"dateTime": item.get("start")}}, "start") if "T" in str(item.get("start")) else _event_time({"start": {"date": item.get("start")}}, "start")
        end = _event_time({"start": {"dateTime": item.get("end")}}, "start") if "T" in str(item.get("end")) else _event_time({"start": {"date": item.get("end")}}, "start")
        if not event_id or not start or not end or end <= start:
            continue
        event = existing.get(event_id)
        if event is None:
            event = CalendarEvent(user_id=user_id, provider_event_id=event_id, source="google")
            db.add(event)
        event.title = item["title"][:200]
        event.start_time = start
        event.end_time = end
        event.description = item.get("description", "")
        event.location = item.get("location", "")[:500]
        event.exercise_type = item["type"]
        event.estimated_duration_min = item["estimated_duration_min"]
        event.estimated_volume = item["estimated_volume"]
        event.ai_insights = item["ai_insights"]
        synced.append(event)

    connection_result = await db.execute(
        select(GoogleCalendarConnection).where(GoogleCalendarConnection.user_id == user_id)
    )
    connection = connection_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if connection is None:
        connection = GoogleCalendarConnection(
            user_id=user_id,
            is_connected=True,
            account_email=None,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
            connected_at=now,
            last_synced_at=now,
        )
        db.add(connection)
    else:
        connection.is_connected = True
        connection.last_synced_at = now
    await db.commit()
    for event in synced:
        await db.refresh(event)

    return CalendarSyncResponse(
        synced_events=[_response(event) for event in synced],
        total_found=len(raw_events),
        workout_events=len(synced),
        sync_timestamp=now,
    )