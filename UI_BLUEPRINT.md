# Fitness AI — UI Blueprint

> **Purpose:** This document gives a UI-building AI agent full context of the backend data contracts, entity display conventions, and page structure for the Fitness AI frontend. Read this before writing any component. Do not infer shapes from field names — every field is explicitly defined here.

---

## Backend Base URL

```
http://localhost:8000/api/v1
```

All endpoints require `Authorization: Bearer {access_token}` except `/auth/register` and `/auth/login`.

---

## Auth

### How authentication works

- Backend issues a **JWT access token** (expires in 60 minutes) and a **refresh token** (expires in 30 days).
- The UI stores both tokens **in memory only** (Zustand store). Never `localStorage`.
- On every API call, attach `Authorization: Bearer {access_token}`.
- If any call returns `401`, silently call `POST /auth/refresh` once, swap the tokens, retry the original call. If refresh also fails, redirect to `/login`.

### Endpoints

**Register**
```
POST /auth/register
Body: { username: string, password: string, email?: string }
Response: { access_token, refresh_token, token_type, expires_in, user_id, username, status }
```

**Login**
```
POST /auth/login
Body: { username: string, password: string }
Response: { access_token, refresh_token, token_type: "bearer", expires_in: number }
```

**Refresh**
```
POST /auth/refresh
Body: { refresh_token: string }
Response: { access_token, refresh_token, token_type, expires_in }
```

**Current user**
```
GET /auth/me
Response: { user_id: string, username: string, email?: string }
```

### How auth is displayed to the user

- `/login` — username + password inputs, submit → tokens stored → redirect to `/dashboard`
- `/register` — username + password + optional email, submit → auto-login → redirect to `/dashboard`
- Every protected page shows the logged-in `username` in the top navigation bar.
- "Sign out" clears the in-memory store and redirects to `/login`.

---

## Entities & Data Contracts

### Enums (use these exact string values everywhere)

```
ExerciseType:  "strength" | "cardio" | "flexibility" | "mixed"
MuscleGroup:   "chest" | "back" | "legs" | "shoulders" | "arms" | "core" | "full_body"
WorkoutStatus: "planned" | "in_progress" | "completed" | "skipped"
```

---

### Entity: WorkoutEntry

A single exercise performed in a session. The backend stores these as rows in Google Sheets (not a relational DB — do not assume an ID per entry).

**Fields sent to the backend (inside `POST /workout/log`):**

| Field | Type | Notes |
|---|---|---|
| `exercise` | string | Free-text name, e.g. `"Bench Press"` |
| `exercise_type` | ExerciseType enum | One of the four enum values |
| `muscle_group` | MuscleGroup enum | Primary muscle group |
| `sets` | integer | Min 1 |
| `reps` | integer | Min 1 |
| `weight_kg` | float | Can be 0 for bodyweight exercises |
| `rpe` | float | Rate of Perceived Exertion, 1–10, step 0.5 |
| `notes` | string? | Optional, per-exercise |
| `form_score` | integer? | Optional, 0–10, populated from form analysis |
| `range_of_motion` | integer? | Optional, 0–100 (percentage) |
| `device_data` | string? | Optional wearable data string |

**Computed fields the backend adds before storing:**

| Field | Formula | Meaning |
|---|---|---|
| `volume` | `sets × reps × weight_kg` | Total load lifted in this entry |
| `one_rm` | `weight_kg × (1 + reps / 30)` | Epley estimated one-rep max |

**How WorkoutEntry is displayed to the user:**

- In the **log form**: one row per exercise. User fills all required fields. Show `volume` and `estimated 1RM` updating live as they type.
- In the **history table**: each row = one entry. Show as `{sets}×{reps} @ {weight_kg}kg`. Volume shown as a separate column.
- In the **progress chart**: x-axis = date, y-axis = `weight_kg`. Multiple entries for the same exercise on different dates become data points on the chart.
- `rpe` is displayed as a coloured indicator: ≤6 = easy (blue), 7–8 = moderate (amber), >8.5 = hard (rose/red).
- `form_score` (if present) is displayed as `{n}/10` with colour: ≥7 = green, 4–6 = amber, <4 = red.

---

### Entity: SessionMetadata

Accompanies every workout log — describes the athlete's physical/mental state for that session.

**Fields sent to the backend (inside `POST /workout/log`):**

| Field | Type | Notes |
|---|---|---|
| `mood` | integer | 1–10 |
| `energy` | integer | 1–10 |
| `sleep_quality` | integer | 1–10 |
| `bodyweight_kg` | float? | Optional |
| `notes` | string? | Optional session notes |

**How SessionMetadata is displayed to the user:**

- In the **log form**: three sliders (mood, energy, sleep_quality) prominently at the top of the form before the exercise rows. These set the context for the whole session.
- In the **history table expanded row**: shown as three small coloured dots or pill badges — "Mood 7 · Energy 6 · Sleep 8".
- On the **dashboard last-session card**: all three shown as a readout for the most recent session.

---

### Entity: WorkoutLogRequest (what we POST to log a session)

This is the full body sent to `POST /workout/log`.

```
POST /workout/log
Body:
{
  user_id: string,          ← from auth store, never ask the user to enter this
  entries: WorkoutEntry[],  ← array of one or more exercises
  session_metadata: {
    mood: integer,
    energy: integer,
    sleep_quality: integer,
    bodyweight_kg?: float,
    notes?: string
  }
}
```

**Response — WorkoutLogResponse:**

```
{
  logged_entries: number,   ← count of entries saved
  total_volume: number,     ← sum of volume across all entries
  insights: EntryInsight[], ← one insight object per entry
  timestamp: string         ← ISO 8601
}
```

**EntryInsight shape:**

```
{
  exercise: string,
  is_pr: boolean,           ← true if weight_kg > previous best for this exercise
  prev_max_kg: number,      ← the previous best (0 if no history)
  form_quality: "good" | "needs_improvement" | "not_recorded",
  suggestion: string        ← coaching suggestion string, always present
}
```

**How the log response is displayed to the user:**

- After a successful log submission, show an **insight panel** (modal or slide-up sheet) with one card per `EntryInsight`.
- If `is_pr` is true: show a prominent "NEW PR 🏆" badge on that card and fire a celebratory toast notification.
- Always show `suggestion` — it is the backend's coaching note (e.g. `"Consider increasing to 85kg next session"`).
- Show `total_volume` as a session summary at the top of the panel.
- After dismissing the panel, invalidate the history and progress query caches so they refetch fresh data.

---

### Entity: HistoryRecord (what comes back from /workout/history)

Each record is one stored exercise entry. The history endpoint returns an array of these.

```
GET /workout/history?days=90&exercise=Bench+Press
Response: HistoryRecord[]
```

**HistoryRecord shape:**

```
{
  date: string,             ← "YYYY-MM-DD"
  user_id: string,
  exercise: string,
  exercise_type: string,    ← ExerciseType enum value
  muscle_group: string,     ← MuscleGroup enum value
  sets: number,
  reps: number,
  weight_kg: number,
  rpe: number,
  volume: number,
  one_rm: number,
  mood: number,
  energy: number,
  sleep_quality: number,
  notes: string,            ← empty string if none
  form_score: number | "",  ← empty string means not recorded
  range_of_motion: number | "",
  device_data: string,
  timestamp: string         ← ISO 8601 full datetime
}
```

**Query parameters:**

| Param | Type | Default | Effect |
|---|---|---|---|
| `days` | integer | 90 | Limit records to the last N days |
| `exercise` | string | (none) | Filter to one exercise name (case-insensitive on backend) |

**How HistoryRecord is displayed to the user:**

- In a **table** on the History page. Each row = one record. Default sort: newest date first.
- Table columns: Date · Exercise · Type badge · `{sets}×{reps} @ {weight_kg}kg` · Volume · RPE · Mood/Energy/Sleep
- Clicking a row expands it to show: `one_rm` ("Est. 1RM: {n}kg"), `form_score` (if not empty string), `range_of_motion` (if not empty string), `notes` (if non-empty).
- `exercise_type` is shown as a coloured badge: strength = lime/green, cardio = sky/blue, flexibility = violet/purple, mixed = amber.
- Filter controls above the table: exercise text search (client-side filter), days select (re-fetches from API).
- CSV export button: converts current filtered records to a CSV and triggers browser download.

---

### Entity: PersonalRecord

Returned as part of `ProgressResponse`. Represents a best-ever performance.

```
{
  exercise: string,
  type: "weight_pr" | "volume_pr" | "one_rm_pr",
  value: number,
  date: string,   ← ISO date string
  reps?: number
}
```

**How PRs are displayed:**

- On the **Progress page**: a row of PR badges below the chart. Each badge shows the type label, the value with units (`{n}kg` for weight/1RM, raw number for volume), and the date.
- `weight_pr` = heaviest single weight lifted for the exercise.
- `volume_pr` = highest volume in one session (sets × reps × weight).
- `one_rm_pr` = highest estimated 1RM (Epley formula) achieved.

---

### Entity: ProgressResponse

Returned by `GET /workout/progress/{exercise}`.

```
GET /workout/progress/{exercise}?days=90
Path param: exercise name (URL-encode spaces as %20)
Query param: days (default 90, options: 30/90/365)

Response:
{
  exercise: string,
  date_range: { start: string, end: string },
  total_workouts: number,
  max_weight: number,
  avg_weight: number,
  max_volume: number,
  avg_volume: number,
  trend: {
    direction: "improving" | "maintaining" | "declining" | "insufficient_data",
    slope: number,       ← kg per session (positive = getting stronger)
    projected_weight: number | null   ← predicted weight 7 sessions from now
  },
  prs: PersonalRecord[]
}
```

**How ProgressResponse is displayed:**

- **Stat tiles row**: Max Weight · Avg Weight · Total Sessions · Max Volume — each as a large number with unit label.
- **Trend indicator**: direction shown as icon + label. `improving` = upward arrow (green). `maintaining` = dash (amber). `declining` = downward arrow (red). `insufficient_data` = hide trend tiles, show note "Log 3+ sessions to see trend analysis".
- **Projected weight**: shown as a dashed line extending past the last data point on the weight chart.
- **PR badges**: one per item in `prs[]` array.
- **Chart**: line chart with date on x-axis, `weight_kg` on y-axis, using data from `/workout/history?exercise={name}&days={n}`. The `ProgressResponse` provides summary stats; the raw points for the chart come from the history endpoint.

---

### Entity: CalendarEvent (Workout Schedule)

The backend reads the user's Google Calendar, detects workout-related events by keyword matching, and returns enriched workout events.

```
POST /workout/schedule/sync?days_ahead=7
(days_ahead is a query param, not a body field)
Body: {} (empty or omit)

Response:
{
  synced_events: CalendarEvent[],
  total_found: number,     ← total calendar events in range
  workout_events: number   ← how many were workout-related
}
```

**CalendarEvent shape:**

```
{
  id: string,
  title: string,
  start: string,           ← ISO datetime string
  end: string,             ← ISO datetime string
  description: string,
  location: string,
  type: string,            ← ExerciseType enum value
  estimated_duration_min: number,
  estimated_volume: number,
  ai_insights: {
    focus_muscles: string[],      ← e.g. ["chest", "anterior deltoid", "triceps"]
    suggested_warmup: string[],   ← e.g. ["Band pull-aparts x 20", "Shoulder rotations x 10"]
    warm_up_time_min: number,
    estimated_duration_min: number,
    type: string
  }
}
```

**How CalendarEvent is displayed:**

- On the **Schedule page**: events grouped by date. Day header above each group (e.g. "Mon, Sep 16").
- Per event card shows: title, time range (`14:00–15:00`), type badge, duration, location (if non-empty), focus muscles as a comma-separated list, and the full suggested warmup as a bulleted list.
- On the **Dashboard**: a horizontal strip of the next 2–3 upcoming workout events. Only title, date/time, type badge, and first 2 warmup suggestions are shown (compact view).
- **Error state**: if the backend has no Google Calendar credentials configured, the API returns an error. The UI must catch this gracefully and show "Google Calendar not connected" — not an error crash.

**Keyword detection (how the backend decides what is a workout event):**
The backend classifies calendar events by checking their title and description text against these keyword groups:
- `cardio` — run, cycling, swim, elliptical, treadmill, hiit, bike
- `strength` — gym, workout, training, lift, weights, squat, bench, deadlift, press, pull, push, row, curl, dip
- `flexibility` — yoga, stretch, mobility, pilates, foam roll

Events not matching any keyword are excluded from the response. Advise users to include these keywords in their calendar event titles.

---

### Entity: PredictionResult

Returned by `GET /workout/predict/{exercise}`. The backend's LSTM model predicts the optimal weight/reps for the next session. **This model is currently a stub on the backend** — it will return a response object but values may be zeroed or placeholder. The UI must handle this gracefully.

```
GET /workout/predict/{exercise}
Response (expected shape — backend may add fields later):
{
  exercise: string,
  predicted_weight: number,
  predicted_reps: number,
  predicted_rpe: number,
  confidence: number        ← 0.0 to 1.0 float
}
```

**How PredictionResult is displayed:**

- On the **Predict page**: a single card showing "Next session for {exercise}" with the predicted weight as a large headline number, predicted reps + RPE as a subline, and a confidence bar (e.g. "82% confidence").
- If `predicted_weight` is 0 or `confidence` is 0: show "Not enough data — log at least 5 sessions for {exercise} to unlock predictions." Hide the prediction card.
- A "Use this prediction" button pre-populates the Log Workout form with the predicted values. The user can edit them before submitting.

---

### Entity: FormAnalysisResult

Returned by `POST /workout/analyze-form`. The backend's pose detection runs on an uploaded video. **This endpoint is a stub** — it will return a response but the computer vision model is not yet active.

```
POST /workout/analyze-form?exercise_type={type}&exercise={name}
Content-Type: multipart/form-data
Field name: "file" (the video file)
Query params: exercise_type (ExerciseType enum), exercise (name string)
Authorization header required.

Response (expected shape):
{
  exercise: string,
  form_score: number,           ← 0–10
  range_of_motion: number,      ← 0–100
  feedback: string,             ← coaching text
  keypoints?: object[]          ← joint coordinates for overlay, may be absent
}
```

**How FormAnalysisResult is displayed:**

- On the **Form Analysis page**: after upload completes, show `form_score` as a large `{n}/10` with colour coding, `range_of_motion` as a percentage bar, and `feedback` as a text block.
- Draw a pose skeleton overlay on top of the video thumbnail using a canvas element. If `keypoints` are present in the response, draw accurate joint positions. If absent, draw a generic placeholder skeleton in a muted colour.
- A "Save to Workout Log" button carries `form_score` and `range_of_motion` into the Log Workout form — pre-fills the matching exercise row's optional fields.
- Stub state: if the response indicates a stub (zeroed values), show "Analysis model not yet active — results are placeholder."

---

## Pages

### Page inventory

| Route | Page Name | Auth required | Primary API calls |
|---|---|---|---|
| `/login` | Login | No | `POST /auth/login` → `GET /auth/me` |
| `/register` | Register | No | `POST /auth/register` |
| `/dashboard` | Dashboard | Yes | `GET /auth/me`, `GET /workout/history?days=7`, `POST /workout/schedule/sync?days_ahead=7` |
| `/log` | Log Workout | Yes | `POST /workout/log` |
| `/schedule` | Calendar Schedule | Yes | `POST /workout/schedule/sync?days_ahead=7` |
| `/progress` | Exercise Progress | Yes | `GET /workout/progress/{exercise}`, `GET /workout/history?exercise={name}&days={n}` |
| `/history` | Workout History | Yes | `GET /workout/history?days={n}&exercise={name}` |
| `/predict` | Predict Session | Yes | `GET /workout/predict/{exercise}` |
| `/form-analysis` | Form Analysis | Yes | `POST /workout/analyze-form` |
| `/coach` | AI Coach | Yes | `POST /coach/chat` (Phase 4 — not built yet) |
| `/program` | Program Builder | Yes | `POST /coach/program` (Phase 4 — not built yet) |

### What each page does (summary)

**Dashboard `/dashboard`**
The landing screen after login. Shows a greeting with the user's name, a "Log Workout" call-to-action, a compact strip of upcoming calendar workout events (next 7 days), and a summary card of the most recent session (date, exercises logged, total volume, mood/energy/sleep readout). In Phase 2, this page also shows training load charts (weekly volume bar chart, muscle group distribution, RPE over time) computed from `/workout/history`.

**Log Workout `/log`**
A form with two sections: (1) Session metadata sliders at the top — mood, energy, sleep quality (all required), optional bodyweight and session notes; (2) A dynamic list of exercise rows — starts with one row, user can add more. Each row has all WorkoutEntry fields. Volume and estimated 1RM update live as the user types. On submit, the `POST /workout/log` response triggers the insight panel overlay. Accepts optional pre-fill via navigation state from the Predict page (`predicted_weight`, `predicted_reps`, `predicted_rpe`) and from the Form Analysis page (`form_score`, `range_of_motion`).

**Calendar Schedule `/schedule`**
Calls `POST /workout/schedule/sync` with a configurable `days_ahead` (7/14/30, user-selectable). Renders the returned workout events grouped by date. Each event card shows full detail including focus muscles and suggested warmup drills. If no Google Calendar credentials are configured on the backend, shows a friendly "Calendar not connected" message with setup instructions — not a crash.

**Exercise Progress `/progress`**
Search for an exercise by name. Shows stat tiles (max weight, avg weight, sessions, max volume), a trend indicator (improving/maintaining/declining), a line chart of weight over time with a projected dashed extension, and PR badges. Uses `GET /workout/progress/{exercise}` for stats + trend + PRs, and `GET /workout/history` for the raw chart data points. Days filter (30/90/365) re-fetches both endpoints.

**Workout History `/history`**
Tabular view of all workout records. Exercise text filter and days selector. Expandable rows showing `one_rm`, `form_score`, `range_of_motion`, `notes`. CSV export of current filtered data. Data comes entirely from `GET /workout/history`.

**Predict Session `/predict`**
Enter an exercise name. Fetches `GET /workout/predict/{exercise}`. Shows the prediction card if data is valid. "Use this prediction" navigates to `/log` with the predicted values pre-filled. Handles stub/zero response with a "not enough data" state.

**Form Analysis `/form-analysis`**
Upload a video file (drag-drop or click) or record directly via browser camera. User selects exercise type and enters exercise name. Submits to `POST /workout/analyze-form` with multipart upload. Shows progress bar during upload. Displays form score, range of motion, feedback text, and pose skeleton overlay on the video thumbnail. "Save to Workout Log" carries scores into the `/log` form.

**AI Coach `/coach` (Phase 4)**
Streaming chat interface. User messages sent to `POST /coach/chat` with a context bundle (recent history, PRs, upcoming calendar events). Coach replies stream token by token via SSE. Not built until Phase 4 backend endpoints exist.

**Program Builder `/program` (Phase 4)**
User selects a goal (strength/hypertrophy/endurance/maintenance) and sessions per week. `POST /coach/program` returns a week of workouts. Each day is editable before the user accepts the program. Not built until Phase 4 backend endpoints exists.

---

## Navigation Structure

**Desktop**: persistent sidebar.
**Mobile**: bottom tab bar.

Primary nav links visible at all times (authenticated):
- Dashboard
- Log Workout (highlighted as the primary action)
- Schedule
- Progress
- History

Secondary nav links (accessible but lower prominence):
- Predict (links to `/predict`)
- Form Analysis (links to `/form-analysis`)
- Coach (links to `/coach` — show "Coming Soon" badge until Phase 4)

---

## Data Flow Rules

1. **`user_id` is always injected from the auth store** — never from a user-facing input field.
2. **Google Sheets is the backend data store for workouts** — not a relational DB. There is no "workout ID" or "session ID" returned. Individual entries cannot be updated or deleted via the API (read-only after log). Build the UI with this in mind: history is append-only.
3. **The `exercise` field is free-text** on input and case-insensitive on the backend match. Suggest adding an exercise autocomplete populated from the user's own history to reduce typos.
4. **`form_score` and `range_of_motion` can be empty strings** in history records (not `null`, not `0`) — always check for empty string before rendering these fields.
5. **Calendar sync is never automatic** — it only runs when the user explicitly triggers it. The UI should not poll it.
6. **TanStack Query cache invalidation rule**: after any successful `POST /workout/log`, invalidate the `['history']` and `['progress']` query cache keys so both pages reflect the new data immediately.
7. **Retry logic**: the backend already has Tenacity retry for Google API calls. The frontend does not need additional retry for Google-related endpoints — a single error response is the final answer.

---

## Error States Reference

| Situation | What to show |
|---|---|
| 401 on any call | Silent refresh attempt, then redirect to `/login` |
| Calendar sync fails (no credentials) | "Google Calendar not connected" — friendly info state, not an error |
| Progress: no data for exercise | "No data for '{exercise}' in the last {n} days. Log a workout to see progress." |
| Progress: fewer than 3 sessions | Chart still shown, but trend tiles hidden. Note: "Log 3+ sessions to see trend." |
| Predict: zero confidence or zero values | "Log at least 5 sessions for {exercise} to unlock predictions." |
| Form analysis: stub response | "Analysis model not yet active — results are placeholder." |
| Coach/Program: 404 endpoint | Hide the feature card entirely — no error shown to user |
| Network offline | Queue workout logs to IndexedDB. Show persistent "Offline — {n} workouts pending sync" banner. |
| Any 5xx server error | Toast: "Something went wrong — try again." Do not expose the raw error detail. |
