# Fitness AI API

FastAPI is the business API for Fitness AI. Supabase Auth provides registered-user identity, and Supabase PostgreSQL stores the exercise catalog, workout sessions, exercise entries, and individual sets. Mobile clients authenticate with Supabase, then send the Supabase access token to this API. The API derives user ownership from the validated token; clients must not send a `user_id` for workout operations.

Google Calendar scheduling and AI Labs endpoints are available for Phase 2. Calendar OAuth tokens are passed per request and are not stored by the API.

## Local Setup

Use Python 3.12 and the existing project environment on Windows:

```powershell
.myenv312\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Configure `.env` with:

- `SUPABASE_URL`: project URL.
- `SUPABASE_ANON_KEY`: Supabase public/anon key used to validate access tokens.
- `DATABASE_URL`: Supabase PostgreSQL connection string using `postgresql+asyncpg`. For Supabase's transaction pooler, use SSL and disable the asyncpg statement cache as shown in `.env.example`.

Before starting the API, run [`scripts/migrate_supabase_workouts.sql`](scripts/migrate_supabase_workouts.sql) once in the Supabase SQL Editor. It preserves existing workout/history tables under `legacy_*` names, creates normalized session/log/set tables, and removes direct anonymous/authenticated table access. It does not delete Supabase Auth users. Review and back up the legacy tables before later dropping them.

Then run [`scripts/migrate_supabase_calendar.sql`](scripts/migrate_supabase_calendar.sql) once. It preserves unowned legacy calendar rows in a locked-down `legacy_calendar_events` table, creates the UUID-owned calendar and connection tables, and installs owner-scoped RLS. Existing legacy events are intentionally not assigned to a user because their ownership cannot be established reliably.

Phase 2 server configuration may include `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` (if required by the OAuth client), `GOOGLE_CALENDAR_ID` (defaults to `primary`), `GEMINI_API_KEY`, and `GEMINI_MODEL` (defaults to `gemini-2.5-flash`). Never put these values in Flutter. To enable form analysis now, create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey), enable the Gemini API for the associated Google project, set `GEMINI_API_KEY` in the backend `.env`, and restart FastAPI. Check the selected model is available to that key/project if Google returns a model-not-found or permission error. Calendar sync requires Google Calendar read access; form analysis returns `503` until the Gemini key is configured.

The app checks database connectivity at startup. It does not create or migrate production tables automatically.

```powershell
.myenv312\Scripts\python.exe -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger UI is available at `http://localhost:8000/docs` in development; health is at `http://localhost:8000/health`.

## Docker

Set the same Supabase values in `.env`, then run:

```powershell
docker compose up --build -d
```

Compose no longer starts a second PostgreSQL database. Redis is retained for the deferred worker phase.

## Public MVP Deployment (Render)

The repository includes [`render.yaml`](render.yaml), which configures a native Python web service with `/health` checks and a lean dependency list in [`requirements-render.txt`](requirements-render.txt). Connect the GitHub repository to Render, select **New → Blueprint**, and create the service from the `main` branch. Set the required secrets in the Render service environment before the first successful deploy:

- `DATABASE_URL`: the Supabase PostgreSQL connection string (use the pooler URL and `ssl=require` as appropriate).
- `SUPABASE_URL` and `SUPABASE_ANON_KEY`: used to validate mobile Supabase access tokens.
- `GEMINI_API_KEY`: optional for MVP workout logging; required for form video analysis.

Run the workout and calendar SQL migrations in the Supabase SQL Editor before expecting database-backed routes to work. `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are optional unless the Google token-refresh flow needs them. Set secrets only in Render's environment settings; never commit `.env`, OAuth JSON, Supabase credentials, or Gemini keys.

Render Free is for demos, not production: services spin down after 15 minutes without traffic and can take about a minute to wake; the filesystem is ephemeral; the free instance has 512 MB RAM. No uploaded workout video is retained by this API, but use short/compressed clips for free-tier reliability. Supabase remains the persistent database. A free Supabase project may also pause when inactive. Verify current provider limits and terms before distributing broadly.

After deploy, test `https://<service-name>.onrender.com/health`, then configure Flutter's `API_BASE_URL` to that HTTPS origin. The first request after idle may be slow because the service is waking.

## Test on a Phone Over Wi-Fi

Start the local API listening on all interfaces:

```powershell
.myenv312\Scripts\python.exe -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Find the development computer's IPv4 address on the same Wi-Fi network (`ipconfig` on Windows), then use `http://<computer-lan-ip>:8000` as the Flutter `API_BASE_URL` on a physical phone. Allow Python/Uvicorn through Windows Defender Firewall on the private network if prompted. Confirm the API first from the phone browser at `/health`. Android Emulator uses `http://10.0.2.2:8000`; iOS Simulator normally uses `http://127.0.0.1:8000`. Do not use a LAN address for production; installed-app testing outside your Wi-Fi should use the Render HTTPS URL.

## Authentication

Sign up and sign in through the Supabase client SDK in the mobile app (email/password or Google provider). Pass the current Supabase access token on API requests:

```http
Authorization: Bearer <supabase-access-token>
```

`GET /api/v1/auth/me` validates the token with Supabase Auth and returns the authenticated profile. FastAPI does not issue or refresh authentication tokens.

## Core API

- `GET /api/v1/exercises?search=bench&muscle_group=chest`: authenticated exercise catalog search.
- `GET /api/v1/exercises/{exercise_id}`: retrieve a catalog exercise.
- `POST /api/v1/exercises`: create a private exercise visible only to its owner.
- `DELETE /api/v1/exercises/{exercise_id}`: delete an owned custom exercise; shared master rows are immutable.
- `POST /api/v1/workout/log`: log one exercise or an entire session in one transaction.
- `GET /api/v1/workout/history?days=90&exercise=Bench&limit=50&offset=0`: user-scoped sessions, with per-set data nested under exercise entries for collapsible history.
- `DELETE /api/v1/workout/sessions/{session_id}`: delete an owned session and its entries/sets.
- `GET /api/v1/workout/progress/{exercise}?days=365`: per-set-derived weight, volume, 1RM trends, and PRs.
- `GET /api/v1/calendar/events?days_ahead=7`: list owned events for 7, 14, or 30 days; optional `start_at` and `end_at` allow an explicit range.
- `POST /api/v1/calendar/events`: create a manual event using `title`, `start`, `end`, optional `description`/`location`, `type`, `estimated_duration_min`, and `estimated_volume`.
- `POST /api/v1/calendar/sync`: sync workout-related events from Google Calendar. Body: `{"access_token":"...","refresh_token":"...","days_ahead":7}`. Tokens are never persisted; a refresh token is optional.
- `GET /api/v1/auth/connections`: return the last verified Google Calendar connection and sync state.
- `GET /api/v1/ai/insights?exercise={exercise_id}`: derive warm-ups and conservative 1RM/next-session estimates from the caller's logged sets.
- `POST /api/v1/ai/analyze-form`: multipart form with `exercise` and exactly one of `video` (video file, up to 100 MB) or `video_url` (public YouTube URL). Private/unlisted videos are not readable by Gemini; upload a local video exported from the phone instead. Uploaded files are deleted from Gemini after analysis and are not stored by FastAPI. Returned coaching feedback is model-generated and is not medical advice.
- `GET /api/v1/ai/training-analysis?days=365&limit=200`: user-scoped longitudinal analysis including every logged set's reps, load, RPE, volume, and estimated 1RM, plus session summaries, exercise trends, and general progression/recovery guidance. Results are bounded to at most 500 sessions per request; `truncated=true` signals that the requested window exceeded the session limit.

Example log request. Parent exercise entries store only total sets and total reps; weights exist only on individual sets:

```json
{
  "entries": [
    {
      "exercise": "Bench Press",
      "exercise_id": "ex-bench-press",
      "exercise_type": "strength",
      "muscle_group": "chest",
      "rpe": 7.5,
      "sets": [
        { "reps": 8, "weight_kg": 60.0, "rpe": 7.0 },
        { "reps": 6, "weight_kg": 65.5, "rpe": 8.0 }
      ]
    }
  ],
  "session_metadata": {
    "mood": 8,
    "energy": 7,
    "sleep_quality": 8,
    "notes": "Morning session"
  }
}
```

The user ID comes from the bearer token and is intentionally absent from the request body. The database applies transactional parent/child constraints and user ownership constraints.

## Verification

```powershell
.myenv312\Scripts\python.exe -m pytest tests -q
```
