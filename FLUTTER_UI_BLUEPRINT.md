# Fitness AI Flutter App Blueprint

## Purpose

This document is the implementation specification for rebuilding the existing Android Fitness AI app as a Flutter app for iOS and Android. Use the Android guide as the feature and visual reference, but build idiomatic Flutter screens rather than mechanically translating Jetpack Compose code.

The mobile app is a client of the existing FastAPI backend. It must not query or mutate workout, exercise, history, profile, or progress tables directly through Supabase PostgREST.

## Product Decisions

- Authentication uses Supabase Auth. Support registered email/password accounts and Google sign-in. There are no guest accounts and no paid-subscription entitlement check.
- Supabase Auth is used by Flutter for sign-up, sign-in, sign-out, OAuth, and token refresh.
- FastAPI is the only business-data API for exercise catalog, workout logging, workout history, deletion, and progress.
- Attach the current Supabase access token to FastAPI requests as `Authorization: Bearer <access_token>`.
- Derive user ownership on the server. Never send a `user_id` in workout or exercise request bodies.
- Workout exercise-entry parents contain `sets_count` and `total_reps`, but no weight. Each individual set contains its own reps and `weight_kg`.
- A saved workout can have one exercise or multiple exercises. The session builder is optional; both quick-log and multi-exercise flows submit the same endpoint.
- Phase 1 contains authentication, dashboard, exercise picker, workout logging, history, and progress.
- Phase 2 contains Google Calendar/scheduling and AI Labs/form analysis/predictions. Do not implement those screens or fake data for them in phase 1.

## AI Coding Agent Rules

When using Cursor or another coding agent, provide it this document and require it to:

1. Read and follow the API contracts below. Do not invent routes or JSON fields.
2. Use the Supabase Flutter SDK only for authentication. All business data goes through FastAPI.
3. Implement one feature slice at a time, including loading, empty, error, success, and expired-session states.
4. Keep secrets out of source control. Flutter may contain the Supabase URL and publishable/anon key; it must never contain a Supabase secret/service-role key or database connection string.
5. Do not translate Compose component-by-component. Use Flutter layout, navigation, and state conventions.
6. Add widget/unit tests for each slice and run analyzer/tests before moving to the next slice.
7. Do not modify the FastAPI contract to suit the UI without first identifying the required backend change and documenting it.

## Recommended Flutter Architecture

Use a feature-first structure with a small shared core:

```text
lib/
  app/
    app.dart
    router.dart
    theme/
  core/
    auth/
    network/
    errors/
    widgets/
    formatting/
  features/
    auth/
    dashboard/
    exercises/
    workout/
    history/
    progress/
    profile/
```

Recommended packages:

- `supabase_flutter` for Supabase Auth and Google OAuth.
- `dio` or `http` for FastAPI calls. Centralize token attachment and error mapping in one API client.
- `flutter_riverpod` for dependency injection and feature state, unless the project already standardizes on another state-management package.
- `go_router` for authenticated/unauthenticated navigation and deep links.
- `fl_chart` for progress line charts.
- `flutter_secure_storage` only if a separate app secret is needed. Let Supabase Flutter manage its own session persistence; do not duplicate access/refresh token storage without a clear need.

Keep API DTOs separate from screen state. Use explicit `fromJson` parsing or generated serialization. Treat numeric values returned by Postgres as JSON numbers that may need conversion to Dart `double`.

## Runtime Configuration

Configure per build environment using `--dart-define` or a non-committed local configuration file:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY` (or legacy anon key)
- `API_BASE_URL`

Never copy backend `.env` values wholesale into Flutter. The FastAPI `DATABASE_URL`, database password, Supabase secret/service-role key, Google credentials, and AI keys must remain server-only.

Local API base URL notes:

- iOS Simulator: `http://127.0.0.1:8000` usually reaches the host machine.
- Android Emulator: use `http://10.0.2.2:8000` to reach the host machine.
- Physical device: use the development machine's LAN IP and ensure the server binds to `0.0.0.0` and the firewall permits the port.
- Production must use HTTPS.

## Navigation and App States

Unauthenticated flow:

- Launch/splash checks the Supabase session.
- No valid session routes to Sign In.
- Sign In links to Sign Up and Google sign-in.
- Successful authentication routes to the authenticated app shell.

Authenticated shell:

- Dashboard
- Log Workout
- History
- Progress
- Profile

Use a bottom navigation bar on compact screens and an appropriate wider navigation layout on tablets. Preserve the active tab when opening an exercise picker or detail flow where sensible. A 401 from FastAPI should trigger one Supabase session refresh/retry if the SDK still has a refreshable session; if refresh fails, clear local auth state and route to Sign In.

Global async states:

- Loading: stable skeleton/progress layout that does not jump when data arrives.
- Empty: explain the relevant next action (e.g., no workouts yet -> log a workout).
- Error: concise message, retry action, and no loss of in-progress form state.
- Offline/network failure: keep staged workout input locally in memory and offer retry; do not claim the server saved it until a successful response arrives.
- Success: show a confirmation/insight summary and invalidate/refetch affected history/progress state.

## Authentication

### Supabase setup

Initialize Supabase Flutter once at app startup with the runtime URL and public key. Use SDK APIs for:

- Email/password sign-up.
- Email/password sign-in.
- Google OAuth sign-in using the Flutter plugin's supported native/deep-link flow.
- Sign-out.
- Current session and token refresh.

Configure Supabase redirect URLs and platform OAuth settings for iOS and Android separately. Handle email confirmation if enabled by the Supabase project. Do not build a FastAPI `/register`, `/login`, `/token`, or `/refresh` flow; those endpoints do not exist in the current backend.

### FastAPI identity check

`GET /api/v1/auth/me`

Headers:

```http
Authorization: Bearer <Supabase access token>
```

Response:

```json
{
  "user_id": "<Supabase Auth UUID>",
  "username": null,
  "email": "athlete@example.com"
}
```

`username` may be null when Supabase user metadata does not contain `username` or `name`. Render email as the reliable account label and use a safe fallback avatar/initials. Do not assume there is a separate profile API.

## API Client Contract

Base URL is environment-dependent, e.g. `http://127.0.0.1:8000` in the iOS Simulator. All business endpoints below require a valid bearer token.

Common behavior:

- Add `Authorization: Bearer <current Supabase access token>` for each request.
- Do not persist a stale token in API configuration; read the current Supabase session token at request time.
- Map `401` to refresh/re-auth handling, `404` to not-found/empty states as appropriate, `409` to duplicate custom exercise feedback, `422` to validation feedback, and `503` to a retryable service/database message.
- Never log authorization headers or passwords.

### Exercise catalog

`GET /api/v1/exercises`

Optional query parameters (combined as AND filters):

- `search`: name substring, 1-100 chars.
- `muscle_group`: `chest`, `back`, `legs`, `shoulders`, `arms`, `core`, `full_body`.
- `exercise_type`: `strength`, `cardio`, `flexibility`, `mixed`.
- `limit`: 1-100, defaults to 50.

Response is an array:

```json
[
  {
    "id": "ex-bench-press",
    "name": "Bench Press",
    "muscle_group": "chest",
    "exercise_type": "strength",
    "default_weight_kg": 70.0,
    "default_sets": 4,
    "default_reps": 8
  }
]
```

Search/filter UI must allow clearing all filters. Do not combine contradictory sample filters. Shared catalog rows are visible to all authenticated users; custom exercises are visible only to their owner. The current catalog has 19 shared seeds; do not assume the 50-item target has already been populated.

`GET /api/v1/exercises/{exercise_id}` retrieves a shared or caller-owned exercise.

`POST /api/v1/exercises` creates a private custom exercise:

```json
{
  "name": "Cable External Rotation",
  "muscle_group": "shoulders",
  "exercise_type": "strength",
  "default_weight_kg": 5,
  "default_sets": 3,
  "default_reps": 12
}
```

Response is one exercise object. Duplicate private names return `409`. Do not show deletion for shared catalog items.

`DELETE /api/v1/exercises/{exercise_id}` deletes only a caller-owned custom exercise. Shared items return not found for this operation.

### Workout logging

`POST /api/v1/workout/log`

The endpoint creates one workout session and all included exercise entries and sets atomically. One entry means a quick single-exercise log; several entries mean one complete session. No `user_id` is accepted. Top-level and entry-level unknown fields are rejected.

Request:

```json
{
  "started_at": "2026-10-10T09:30:00Z",
  "entries": [
    {
      "exercise": "Bench Press",
      "exercise_id": "ex-bench-press",
      "exercise_type": "strength",
      "muscle_group": "chest",
      "rpe": 7.5,
      "notes": "Felt strong",
      "form_score": null,
      "range_of_motion": null,
      "device_data": {},
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
    "bodyweight_kg": 75.5,
    "notes": "Morning workout"
  }
}
```

Validation constraints:

- 1-100 entries.
- Exercise name 2-100 characters.
- Each entry has 1-100 sets.
- Set reps 0-1000 and weight 0-1000 kg.
- RPE 1-10 when supplied.
- Mood, energy, sleep quality 1-10.
- Optional bodyweight 20-300 kg.
- For bodyweight movements, send `weight_kg: 0` if that is the intended load representation.

Response (`201 Created`):

```json
{
  "status": "success",
  "session_id": "<UUID>",
  "logged_entries": 1,
  "total_volume": 873.0,
  "insights": [
    {
      "exercise": "Bench Press",
      "is_pr": true,
      "prev_max_kg": 0.0,
      "form_quality": "not_recorded",
      "suggestion": "New weight personal record."
    }
  ],
  "timestamp": "2026-10-10T09:30:00+00:00"
}
```

Volume is calculated as the sum of `reps * weight_kg` over child sets. The exercise parent does not accept or contain weight; its `sets_count` and `total_reps` are computed by the server.

In the UI, let a user build/edit the staged entries and per-set rows locally before submission. Submitting a batch writes all entries in one request. Do not call the API once per set. On success, clear the staged builder and refresh dashboard/history/progress data. On failure, retain the staged form for retry.

### Workout history

`GET /api/v1/workout/history`

Query parameters:

- `days`: 1-3650, default 90.
- `exercise`: optional name substring.
- `muscle_group`: optional category value.
- `limit`: 1-100, default 50.
- `offset`: zero or greater, default 0.

Response:

```json
{
  "records": [
    {
      "id": "<session UUID>",
      "started_at": "2026-10-10T09:30:00+00:00",
      "completed_at": "2026-10-10T09:32:00+00:00",
      "mood": 8,
      "energy": 7,
      "sleep_quality": 8,
      "bodyweight_kg": 75.5,
      "notes": "Morning workout",
      "exercise_count": 1,
      "total_volume": 873.0,
      "entries": [
        {
          "id": 1,
          "exercise_id": "ex-bench-press",
          "exercise": "Bench Press",
          "exercise_type": "strength",
          "muscle_group": "chest",
          "sets_count": 2,
          "total_reps": 14,
          "rpe": 7.5,
          "notes": "Felt strong",
          "form_score": null,
          "range_of_motion": null,
          "volume": 873.0,
          "estimated_1rm": 78.6,
          "sets": [
            { "id": "<set UUID>", "set_number": 1, "reps": 8, "weight_kg": 60.0, "rpe": 7.0 },
            { "id": "<set UUID>", "set_number": 2, "reps": 6, "weight_kg": 65.5, "rpe": 8.0 }
          ]
        }
      ]
    }
  ],
  "count": 1,
  "limit": 50,
  "offset": 0
}
```

History layout:

- One top-level card/row per session, newest first.
- Compact summary shows date, exercise count, volume, and session vitals.
- Each exercise entry shows name, `sets_count x total_reps`, muscle group, RPE, volume, and estimated 1RM. Do not display a parent-level weight.
- Tapping/expanding the exercise reveals each child set’s number, reps, weight, and set RPE.
- Filtering by exercise or muscle group still returns matching sessions; render the entries included in each response without assuming a separate history-record endpoint.
- Pagination uses `limit`/`offset`. Provide a sensible load-more pattern.

Delete a whole session:

`DELETE /api/v1/workout/sessions/{session_id}`

Delete one exercise entry while preserving sibling entries in its session:

`DELETE /api/v1/workout/entries/{entry_id}`

Both return `{"status":"deleted"}`. Confirm destructive user actions and refresh affected data. Deleting the only entry also deletes the now-empty session.

### Progress and analytics

`GET /api/v1/workout/progress/{exercise}?days=365`

`days` must be between 7 and 3650. Exercise is matched case-insensitively. A no-history response is `404` and should display a helpful empty state, not a generic error.

Response shape:

```json
{
  "exercise": "Bench Press",
  "date_range": { "start": "<ISO timestamp>", "end": "<ISO timestamp>" },
  "total_workouts": 12,
  "max_weight": 80.0,
  "avg_weight": 72.5,
  "max_volume": 2560.0,
  "avg_volume": 1900.0,
  "trend": {
    "direction": "improving",
    "slope": 0.42,
    "projected_weight": 82.5
  },
  "prs": [
    { "type": "weight_pr", "value": 80.0, "date": "<ISO timestamp>" },
    { "type": "volume_pr", "value": 2560.0, "date": "<ISO timestamp>" },
    { "type": "1rm_pr", "value": 86.4, "date": "<ISO timestamp>" }
  ],
  "points": [
    { "date": "<ISO timestamp>", "max_weight": 80.0, "volume": 2560.0, "one_rm": 86.4 }
  ]
}
```

Render exercise selection from the exercise catalog, a 30/90/365-day range selector, stat summaries, chart points, trend, and PR list. The backend currently returns max and average weight/volume, PRs, and one point per logged entry. It does not provide a total session count across all exercises or dashboard aggregates; do not invent those endpoints. A dashboard can derive recent session count/total volume/recent session from history pages, but clearly scope those aggregates to fetched data unless all history is paginated.

## Screen Specifications

### 1. Sign In and Sign Up

- Email/password input, validation, show/hide password, submit/loading state, and clear error text.
- Sign-up can request username as Supabase user metadata if desired, but profile display must support missing metadata.
- Google sign-in through Supabase Flutter native OAuth flow.
- Include email-confirmation messaging if the Supabase project requires confirmation.
- Never send credentials to FastAPI.

### 2. Dashboard

- Personalized greeting using profile email/name metadata, with a fallback when username is null.
- Primary “Start Workout” action navigates to Log Workout.
- Recent session and summary stats derived from `/workout/history`; avoid pretending partial pagination is an all-time aggregate.
- Recent PRs may be derived from selected exercise progress responses. Do not issue an unbounded N+1 request for every exercise; load only a deliberate small set or defer the PR showcase until a suitable backend endpoint exists.
- No Calendar strip in phase 1.

### 3. Log Workout

- Exercise picker opens from an obvious search action and uses `/api/v1/exercises`.
- Allow a custom exercise through `POST /api/v1/exercises` without leaving the flow; refresh catalog after success.
- Selected exercise fills defaults for sets/reps/weight, but the user can edit all sets independently.
- Each set row has editable reps, editable `weight_kg`, optional RPE, add-set and remove-set actions.
- Entry-level RPE, notes, form score, range of motion, and device data are optional.
- Display live volume as `sum(set reps * set weight)` and estimated 1RM using the highest per-set Epley result; these are previews only, computed on device.
- Session check-in fields are mood, energy, sleep quality, optional bodyweight, and notes.
- Offer “Log this exercise” and an optional session builder. Both use `POST /api/v1/workout/log`; quick-log sends one entry, session save sends all staged entries at once.
- Prevent submission with no entries or no sets. Avoid losing staged data on transient failures.
- After success show total volume and per-exercise PR/form feedback returned by the API.

### 4. History

- Date range, exercise text, and muscle-group filters; loading and no-results states.
- Session rows/cards expand to exercise entries; entries expand to per-set detail.
- Parent summary displays total sets and total reps, never a parent weight.
- Include delete-entry and delete-session actions with confirmation.
- Add pagination/load more using the API limit/offset.
- CSV export can be generated locally from fetched history pages; label/export only records actually fetched unless all pages were collected successfully.

### 5. Progress

- Exercise selector fed by the catalog and window selection (30, 90, 365 days).
- Show max weight, average session max weight, total logged exercise entries, and max volume as provided by the endpoint.
- Chart the `points` list for max weight; optionally allow switching to volume or estimated 1RM using the same points.
- Show trend direction/slope/projection and three PR categories.
- Empty state on 404 and retry on network errors.

### 6. Profile

- Show email, Supabase user ID only where useful for diagnostics, and username/name metadata if present.
- Sign out through Supabase SDK, clear app state/cache, and return to Sign In.
- Metric units are the backend canonical unit (`kg`). If the UI offers pounds, convert for display/input only and convert back to kilograms before API submission. Do not store pounds in API requests.
- Google connection status and account linking belong to phase 2.

### 7. Phase 2 API contracts

Phase 2 backend contracts are available. Keep Phase 1 scope as specified above; implement Phase 2 screens only when explicitly scheduled. Do not use fake responses for Calendar or AI Labs.

`GET /api/v1/ai/training-analysis?days=365&limit=200`

- Authenticated, user-scoped analysis of completed workout sessions. `days` is 7-3650; `limit` is 1-500 sessions. `truncated` signals more sessions existed than were included.
- The response contains each session, each exercise entry, and every set's `reps`, `weight_kg`, optional `rpe`, `volume_kg_reps`, and `estimated_1rm_kg`. Exercise summaries include estimated 1RM and volume change, trend classification, and conservative general guidance.
- This first release has no user goals and does not claim to predict individual outcomes. Treat estimates as training signals, preserve empty-data/limited-history states, and show that comparisons are most useful with consistent exercise technique and range of motion.
- A future goal-analysis slice can add goal selection, target dates, goal-specific milestones, and goal-aware recommendations. Do not send or infer goals until that contract is designed.

`POST /api/v1/ai/analyze-form`

- Send multipart form data with `exercise` and exactly one of `video` or `video_url`.
- Phone/local video uploads are limited to 100 MB and accepted formats are MP4, MPEG, MOV, AVI, FLV, MPG, WebM, WMV, and 3GPP. Uploaded files are passed to Gemini Files API and deleted after analysis.
- URL mode supports public YouTube URLs only. Private or unlisted links cannot be accessed by Gemini; tell the user to choose the local upload option instead. Handle 413 (over 100 MB), 415 (unsupported video type), 422 (invalid source), 503 (model not configured), and 502 (provider failure) with actionable messages.
- FastAPI requires server-only `GEMINI_API_KEY`; `GEMINI_MODEL` defaults to `gemini-2.5-flash`. Never put the key in Flutter or return it in errors/logs. Model-generated form observations are not medical advice.

Calendar Phase 2 endpoints are `GET/POST /api/v1/calendar/events`, `POST /api/v1/calendar/sync`, and `GET /api/v1/auth/connections`. Calendar and AI endpoints require the current Supabase access token.

## Visual and Interaction Guidance

- Preserve the Android app’s functional identity: quick between-set interactions, numeric controls that are easy to tap, clear exercise/set hierarchy, compact readable summaries, and distinct success/error feedback.
- Define a consistent theme with semantic color roles for primary action, surfaces, success, warning, error, and RPE intensity. Keep text contrast accessible.
- Use large enough tap targets for gym use and avoid dense tiny controls. Keep set rows aligned and stable when values change.
- Prefer familiar controls: segmented controls for time ranges, chips for exercise/muscle filters, steppers for numeric changes, text/numeric fields for direct edits, and expansion tiles/accordions for set details.
- Support keyboard dismissal, safe areas, screen readers, dynamic text, and narrow phones. Verify that dialogs and set editors remain usable with the keyboard open.
- Do not use decorative marketing/landing content. The first screen after sign-in should be the working fitness dashboard.

## Implementation Milestones and Acceptance Checks

### Milestone 1: App shell and authentication

- Flutter app builds for iOS and Android.
- Session restoration routes correctly to authenticated or unauthenticated shell.
- Email sign-up/sign-in, Google sign-in, sign-out, and email confirmation handling work with the configured Supabase project.
- `/api/v1/auth/me` succeeds with the SDK access token; no token or password appears in logs.

### Milestone 2: Exercise catalog

- Search, muscle/type filtering, clear filters, empty state, and retry work.
- Shared exercise can be selected and custom exercise can be created.
- Custom exercise delete is offered only for caller-created items.

### Milestone 3: Workout logging

- Per-set reps/weight edits, set add/remove, entry add/remove, metadata, live calculations, and validation work.
- A single exercise and a multi-exercise session each create data through one `POST /workout/log` call.
- No request contains `user_id` or parent-level `weight_kg`.
- Failed submission retains the staged workout; successful submission clears it and displays returned insights.

### Milestone 4: History

- Sessions, exercise summaries, and collapsible individual sets display correctly.
- Filters and pagination work; session and entry deletion refresh the list.
- User A cannot see User B history after signing in as each account.

### Milestone 5: Progress and polish

- Progress filters call the expected endpoint and chart its returned points.
- Empty/no-history, offline, server error, and sign-out states are handled.
- Test on iOS Simulator, Android Emulator, and at least one narrow physical-device viewport if available.
- Run `flutter analyze`, unit/widget tests, and a short manual acceptance pass for every milestone before feature completion.

## Cursor Starter Prompt

```text
Build the Fitness AI Flutter app according to FLUTTER_UI_BLUEPRINT.md. First inspect the existing repository and report whether a Flutter project already exists. Do not modify FastAPI unless I explicitly ask. Implement only Milestone 1 (app shell and Supabase authentication) in this task, including loading/error/success states and tests. Use Supabase Flutter only for authentication, and do not access business tables through Supabase. Read API base URL and Supabase URL/public key from build-time configuration; never add secrets to source. At the end, list changed files, commands run, test results, and remaining configuration I must supply.
```
