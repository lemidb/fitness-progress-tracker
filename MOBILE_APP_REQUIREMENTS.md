# Fitness AI Mobile App — Product Requirements Document (PRD)

**Version:** 1.0  
**Last Updated:** September 3, 2026  
**Project:** Fitness AI Mobile Client (iOS & Android)  
**Backend API:** FastAPI v1.0 (Phase 1 Complete)

---

## 1. Executive Summary

### 1.1 Product Overview
A mobile application for iOS and Android that connects to the Fitness AI backend API, enabling users to log workouts in real-time at the gym, track progress over time, sync with Google Calendar for workout scheduling, and receive AI-powered coaching insights.

### 1.2 Target Users
- **Primary:** Gym-goers who track strength training workouts (18-45 years old)
- **Secondary:** Personal trainers managing client workout logs
- **Tertiary:** Fitness enthusiasts tracking cardio and flexibility routines

### 1.3 Core Value Proposition
Transform gym workout tracking from tedious spreadsheet logging to a seamless mobile experience with intelligent insights, automatic syncing, and progress visualization — all while users are at the gym between sets.

---

## 2. Technical Context

### 2.1 Backend API (Already Built)
- **Base URL:** `https://api.fitness-ai.com` (configurable per environment)
- **Authentication:** JWT Bearer tokens (access + refresh token flow)
- **API Documentation:** Swagger UI at `/docs`, ReDoc at `/redoc`
- **Protocol:** REST over HTTPS
- **Data Format:** JSON

### 2.2 Existing API Endpoints

#### **Authentication Endpoints**
| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---------------|
| POST | `/api/v1/auth/register` | Create new user account | No |
| POST | `/api/v1/auth/login` | Login with username/password | No |
| POST | `/api/v1/auth/token` | Dev token generation | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | No |
| GET | `/api/v1/auth/me` | Get current user profile | Yes |

#### **Workout Endpoints**
| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---------------|
| POST | `/api/v1/workout/log` | Log completed workout session | Yes |
| POST | `/api/v1/workout/schedule/sync` | Sync Google Calendar workouts | Yes |
| GET | `/api/v1/workout/progress/{exercise}` | Get exercise performance analytics | Yes |
| GET | `/api/v1/workout/history` | Fetch workout history | Yes |
| POST | `/api/v1/workout/analyze-form` | Upload video for form analysis (Phase 3) | Yes |
| GET | `/api/v1/workout/predict/{exercise}` | Get LSTM workout predictions (Phase 2) | Yes |

### 2.3 Data Models (from Backend)

#### **WorkoutEntry**
```json
{
  "exercise": "Bench Press",
  "sets": 4,
  "reps": 8,
  "weight_kg": 80.0,
  "rpe": 7.5,
  "exercise_type": "strength",  // enum: strength | cardio | flexibility | mixed
  "muscle_group": "chest",      // enum: chest | back | legs | shoulders | arms | core | full_body
  "notes": "Felt strong today",
  "form_score": 8.5,            // optional, 0-10
  "range_of_motion": 95.0,      // optional, 0-100%
  "device_data": ""             // optional, JSON string for future device integrations
}
```

#### **SessionMetadata**
```json
{
  "mood": 8,                    // 1-10
  "energy": 7,                  // 1-10
  "sleep_quality": 8,           // 1-10
  "bodyweight_kg": 75.5,        // optional
  "notes": "Morning session"
}
```

#### **WorkoutLogRequest** (POST /workout/log)
```json
{
  "user_id": "uuid-string",
  "entries": [WorkoutEntry, ...],  // 1+ exercises
  "session_metadata": SessionMetadata
}
```

#### **WorkoutLogResponse**
```json
{
  "status": "success",
  "logged_entries": 3,
  "total_volume": 2400.0,       // sum of (sets × reps × weight) across all entries
  "insights": [                 // per-exercise AI insights
    {
      "exercise": "Bench Press",
      "is_pr": true,
      "prev_max_kg": 75.0,
      "form_quality": "good",   // good | needs_improvement | not_recorded
      "suggestion": "Consider increasing to 84kg next session"
    }
  ],
  "timestamp": "2026-09-03T08:15:00Z"
}
```

#### **ScheduleSyncResponse** (POST /workout/schedule/sync)
```json
{
  "status": "success",
  "schedule": [
    {
      "id": "event-id-123",
      "title": "Leg Day",
      "start": "2026-09-04T07:00:00Z",
      "end": "2026-09-04T08:30:00Z",
      "description": "Squats, lunges, leg press",
      "location": "Gold's Gym",
      "type": "strength",
      "estimated_duration_min": 90,
      "estimated_volume": 0,
      "ai_insights": {
        "focus_muscles": ["quadriceps", "glutes", "hamstrings"],
        "suggested_warmup": ["Goblet squats x 10 (light)", "Hip circles x 10", "Leg swings x 10"],
        "warm_up_time_min": 10,
        "estimated_duration_min": 90,
        "type": "strength"
      }
    }
  ],
  "total_workouts": 3,
  "sync_timestamp": "2026-09-03T08:15:00Z"
}
```

#### **ProgressResponse** (GET /workout/progress/{exercise})
```json
{
  "exercise": "Bench Press",
  "date_range": {
    "start": "2026-06-01T00:00:00",
    "end": "2026-09-03T00:00:00"
  },
  "total_workouts": 24,
  "max_weight": 80.0,
  "avg_weight": 72.5,
  "max_volume": 2560.0,
  "avg_volume": 2240.0,
  "trend": {
    "direction": "improving",   // improving | declining | maintaining | insufficient_data
    "slope": 0.42,
    "projected_weight": 82.5
  },
  "prs": [
    {
      "exercise": "Bench Press",
      "type": "weight_pr",
      "value": 80.0,
      "date": "2026-09-01T00:00:00",
      "reps": 8
    },
    {
      "type": "volume_pr",
      "value": 2560.0,
      "date": "2026-09-01T00:00:00"
    },
    {
      "type": "one_rm_pr",
      "value": 101.3,
      "date": "2026-09-01T00:00:00",
      "reps": 8
    }
  ]
}
```

#### **HistoryResponse** (GET /workout/history)
```json
{
  "records": [
    {
      "date": "2026-09-01",
      "user_id": "uuid",
      "exercise": "Bench Press",
      "exercise_type": "strength",
      "muscle_group": "chest",
      "sets": 4,
      "reps": 8,
      "weight_kg": 80.0,
      "rpe": 7.5,
      "volume": 2560.0,
      "one_rm": 101.3,
      "mood": 8,
      "energy": 7,
      "sleep_quality": 8,
      "notes": "",
      "form_score": "",
      "range_of_motion": "",
      "device_data": "",
      "timestamp": "2026-09-01T09:30:00Z"
    }
  ],
  "count": 24
}
```

### 2.4 Authentication Flow
1. User registers via `/auth/register` → receive `access_token` + `refresh_token`
2. Store tokens securely (iOS Keychain / Android Keystore)
3. Include `Authorization: Bearer {access_token}` header in all protected requests
4. When access token expires (60 min), call `/auth/refresh` with `refresh_token`
5. Refresh token valid for 30 days
6. On 401 Unauthorized, force re-login

---

## 3. Feature Requirements

### 3.1 Phase 1 (MVP) — Core Workout Tracking

#### **FR-1.1: User Registration & Authentication**
- **Priority:** P0 (Must Have)
- **Description:** Users can create accounts and authenticate to access their workout data
- **User Stories:**
  - As a new user, I want to register with username/email/password
  - As a returning user, I want to log in with my credentials
  - As a logged-in user, I want my session to persist between app launches
  - As a user, I want to see my profile information

**Acceptance Criteria:**
- ✅ Registration screen with validation (username 3+ chars, password 8+ chars, valid email)
- ✅ Login screen with "Remember Me" toggle
- ✅ Secure token storage (Keychain/Keystore)
- ✅ Automatic token refresh on 401 responses
- ✅ Logout functionality clears stored tokens
- ✅ Profile screen displays username and email from `/auth/me`

---

#### **FR-1.2: Workout Logging Interface**
- **Priority:** P0 (Must Have)
- **Description:** Quick and efficient workout entry while at the gym between sets
- **User Stories:**
  - As a user, I want to start a new workout session
  - As a user, I want to add exercises one by one during my workout
  - As a user, I want to log sets/reps/weight for each exercise
  - As a user, I want to rate my RPE (Rate of Perceived Exertion) per exercise
  - As a user, I want to specify muscle group and exercise type
  - As a user, I want to complete my session and see a summary

**Acceptance Criteria:**
- ✅ "Start Workout" button on home screen
- ✅ Exercise search/autocomplete (from common exercises database)
- ✅ Quick entry form: Exercise Name, Sets (spinner/stepper), Reps (spinner/stepper), Weight (number pad with kg/lbs toggle)
- ✅ RPE slider (1-10 with 0.5 increments)
- ✅ Muscle group picker (dropdown/chips: chest, back, legs, shoulders, arms, core, full_body)
- ✅ Exercise type picker (dropdown: strength, cardio, flexibility, mixed)
- ✅ Optional "Add Notes" text field per exercise
- ✅ "Add Another Exercise" button during session
- ✅ "Complete Workout" button → shows session summary modal
- ✅ Session summary displays: total volume, exercise count, duration, insights from API
- ✅ Ability to edit/delete exercises before completing session
- ✅ Loading state while API call is in progress
- ✅ Success/error messages after logging

**UI/UX Requirements:**
- Large touch targets (minimum 44x44pt on iOS, 48x48dp on Android)
- One-handed operation optimized (bottom-sheet modals, FABs)
- Dark mode support (for low-light gym environments)
- Haptic feedback on successful exercise additions
- Swipe-to-delete exercises from current session list

---

#### **FR-1.3: Session Metadata Capture**
- **Priority:** P1 (Should Have)
- **Description:** Capture contextual data that affects workout performance
- **User Stories:**
  - As a user, I want to record my mood/energy/sleep before starting a workout
  - As a user, I want to optionally log my bodyweight for tracking

**Acceptance Criteria:**
- ✅ Pre-workout screen (shown after tapping "Start Workout"):
  - Mood slider (1-10, emoji indicators: 😞 → 😊)
  - Energy slider (1-10, emoji indicators: 🔋 → ⚡)
  - Sleep quality slider (1-10, emoji indicators: 😴 → ✨)
  - Optional bodyweight input (kg/lbs with unit toggle)
  - Optional session notes text field
- ✅ "Skip" button to bypass metadata (defaults to 5/5/5)
- ✅ Metadata editable from session summary before final submission

---

#### **FR-1.4: Workout History View**
- **Priority:** P0 (Must Have)
- **Description:** View past workout sessions and individual exercise history
- **User Stories:**
  - As a user, I want to see a chronological list of my past workouts
  - As a user, I want to filter history by exercise name
  - As a user, I want to see details of a past workout session

**Acceptance Criteria:**
- ✅ "History" tab in bottom navigation
- ✅ List view grouped by date (newest first)
- ✅ Each history item shows: date, exercise count, total volume, session duration (if tracked)
- ✅ Search bar to filter by exercise name
- ✅ Tap history item → detail view showing all exercises with sets/reps/weight/RPE
- ✅ Date range filter (Last 7 days / 30 days / 90 days / All time)
- ✅ Pull-to-refresh to fetch latest data
- ✅ Infinite scroll / pagination for long histories
- ✅ Empty state when no data exists

---

#### **FR-1.5: Exercise Progress Analytics**
- **Priority:** P1 (Should Have)
- **Description:** Visual progress tracking for individual exercises
- **User Stories:**
  - As a user, I want to see my progress for a specific exercise over time
  - As a user, I want to see my personal records (PRs)
  - As a user, I want to see trends (improving/maintaining/declining)
  - As a user, I want projected weight recommendations

**Acceptance Criteria:**
- ✅ Exercise detail screen accessible from history or search
- ✅ Line chart showing weight progression over time
- ✅ PR badges displayed prominently:
  - Weight PR (heaviest single-set weight)
  - Volume PR (highest single-session volume)
  - Estimated 1RM PR
- ✅ Trend indicator with visual cues (↗️ improving, ➡️ maintaining, ↘️ declining)
- ✅ Stats summary card:
  - Total workouts logged
  - Max weight ever lifted
  - Average weight (last 90 days)
  - Projected next weight (from trend analysis)
- ✅ Date range selector (30/60/90/365 days)
- ✅ Chart is scrollable/zoomable for large datasets

**Data Visualization:**
- Use lightweight charting library (e.g., react-native-chart-kit, Victory Native)
- X-axis: dates, Y-axis: weight (kg/lbs)
- Plot points for each workout, connect with line
- Highlight PRs with different colored markers

---

#### **FR-1.6: Google Calendar Integration**
- **Priority:** P1 (Should Have)
- **Description:** Sync upcoming workout schedule from Google Calendar
- **User Stories:**
  - As a user, I want to see my planned workouts from my calendar
  - As a user, I want AI-generated warmup suggestions for scheduled workouts
  - As a user, I want to quickly start a workout from a calendar event

**Acceptance Criteria:**
- ✅ "Schedule" tab in bottom navigation
- ✅ Calendar view showing next 7 days (default)
- ✅ Each workout card displays:
  - Event title
  - Date & time
  - Workout type (strength/cardio/flexibility badge)
  - Estimated duration
  - Location (if set)
- ✅ Expandable card shows AI insights:
  - Focus muscles
  - Suggested warmup exercises
  - Warmup duration estimate
- ✅ "Start This Workout" button → opens workout logging with pre-filled metadata
- ✅ Pull-to-refresh to re-sync with Google Calendar
- ✅ "Sync Settings" link to adjust days_ahead (7/14/30 days)
- ✅ Empty state when no upcoming workouts found
- ✅ Offline mode shows last cached schedule with "Offline" indicator

---

#### **FR-1.7: Exercise Library & Search**
- **Priority:** P1 (Should Have)
- **Description:** Searchable database of common exercises for quick logging
- **User Stories:**
  - As a user, I want to search for exercises by name
  - As a user, I want to see my recently used exercises first
  - As a user, I want to add custom exercises not in the library

**Acceptance Criteria:**
- ✅ Exercise picker with search bar (debounced, 300ms delay)
- ✅ Recent exercises section (last 10 used)
- ✅ Popular exercises section (pre-defined list of common lifts)
- ✅ Exercises grouped by muscle group (collapsible sections)
- ✅ "Add Custom Exercise" button → manual text entry
- ✅ Exercise autocomplete shows exercise type icon (🏋️ strength, 🏃 cardio, 🧘 flexibility)
- ✅ Search results include aliases (e.g., "bench" matches "Bench Press", "Barbell Bench Press")

**Pre-Defined Exercise Library (Minimum 50 exercises):**
- **Chest:** Bench Press, Incline Bench Press, Dumbbell Fly, Cable Crossover, Push-ups
- **Back:** Deadlift, Barbell Row, Pull-ups, Lat Pulldown, Seated Cable Row, T-Bar Row
- **Legs:** Squat, Front Squat, Leg Press, Romanian Deadlift, Lunges, Leg Curl, Leg Extension
- **Shoulders:** Overhead Press, Lateral Raise, Front Raise, Face Pull, Arnold Press
- **Arms:** Barbell Curl, Hammer Curl, Tricep Dip, Skull Crusher, Cable Curl
- **Core:** Plank, Crunches, Russian Twist, Leg Raise, Ab Wheel
- **Cardio:** Treadmill Run, Cycling, Rowing Machine, Elliptical, Jump Rope
- **Flexibility:** Yoga Flow, Static Stretching, Dynamic Stretching

---

### 3.2 Phase 2 (Enhanced Features) — Post-MVP

#### **FR-2.1: Offline Mode**
- **Priority:** P1 (Should Have)
- **Description:** Log workouts without internet, sync when connection restored
- **Acceptance Criteria:**
  - ✅ Workout logs saved to local SQLite/Realm database
  - ✅ Auto-sync when network available (background queue)
  - ✅ Sync status indicator in UI
  - ✅ Conflict resolution (server state wins)

#### **FR-2.2: Rest Timer**
- **Priority:** P2 (Nice to Have)
- **Description:** Built-in timer for rest periods between sets
- **Acceptance Criteria:**
  - ✅ Configurable rest duration (30s/60s/90s/120s/custom)
  - ✅ Visual countdown timer
  - ✅ Audio/haptic alert when rest complete
  - ✅ Auto-start option after completing a set

#### **FR-2.3: Plate Calculator**
- **Priority:** P2 (Nice to Have)
- **Description:** Calculate which plates to load on barbell for target weight
- **Acceptance Criteria:**
  - ✅ Input target weight → shows plate configuration
  - ✅ Supports standard plates (2.5kg, 5kg, 10kg, 15kg, 20kg, 25kg)
  - ✅ Accounts for bar weight (20kg Olympic bar default, customizable)
  - ✅ Kg/lbs toggle

#### **FR-2.4: Workout Templates**
- **Priority:** P2 (Nice to Have)
- **Description:** Save and reuse common workout routines
- **Acceptance Criteria:**
  - ✅ "Save as Template" option after completing workout
  - ✅ Templates library screen
  - ✅ "Start from Template" → pre-fills exercises
  - ✅ Edit/delete templates

#### **FR-2.5: Push Notifications**
- **Priority:** P2 (Nice to Have)
- **Description:** Reminders for scheduled workouts and rest days
- **Acceptance Criteria:**
  - ✅ Opt-in permission prompt on first launch
  - ✅ Notification 1 hour before scheduled workout (from Calendar sync)
  - ✅ Daily summary notification (total volume logged today)
  - ✅ Celebration notifications for new PRs
  - ✅ Notification settings screen (enable/disable by type)

---

### 3.3 Phase 3 (AI-Powered Features) — Future

#### **FR-3.1: Video Form Analysis**
- **Priority:** P2 (Future)
- **Description:** Upload workout video for AI pose estimation feedback
- **Acceptance Criteria:**
  - ✅ Video upload from camera roll or record in-app
  - ✅ Exercise type selection (squat/bench/deadlift/etc.)
  - ✅ API call to `/workout/analyze-form`
  - ✅ Display form score, joint angle analysis, recommendations

#### **FR-3.2: LSTM Workout Predictions**
- **Priority:** P2 (Future)
- **Description:** Predict recommended weight/reps for next workout
- **Acceptance Criteria:**
  - ✅ "Get Recommendation" button on exercise detail screen
  - ✅ API call to `/workout/predict/{exercise}`
  - ✅ Display predicted weight, reps, confidence interval

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **NFR-1:** App launch to main screen < 2 seconds on mid-range devices
- **NFR-2:** Workout logging API call < 3 seconds on 4G connection
- **NFR-3:** Smooth 60fps scrolling in history list with 100+ entries
- **NFR-4:** Chart rendering < 1 second for 365 days of data

### 4.2 Security
- **NFR-5:** JWT tokens stored in iOS Keychain / Android Keystore (never UserDefaults/SharedPreferences)
- **NFR-6:** All API calls over HTTPS (certificate pinning optional)
- **NFR-7:** Biometric authentication option (Face ID / Touch ID / Fingerprint)
- **NFR-8:** Auto-logout after 30 days of inactivity

### 4.3 Usability
- **NFR-9:** Support iOS 15+ and Android 8.0+ (API level 26+)
- **NFR-10:** Full accessibility support (VoiceOver, TalkBack, Dynamic Type)
- **NFR-11:** Dark mode matches system preference
- **NFR-12:** Internationalization support (initial: English only, structure for localization)
- **NFR-13:** Kg/lbs unit preference persisted per user

### 4.4 Compatibility
- **NFR-14:** Work on screen sizes from iPhone SE (4.7") to iPad Pro (12.9")
- **NFR-15:** Work on Android phones and tablets (320dp to 1024dp width)
- **NFR-16:** Graceful degradation when backend APIs return 5xx errors

### 4.5 Data & Privacy
- **NFR-17:** Comply with GDPR (EU users can request data deletion)
- **NFR-18:** No analytics/tracking without explicit user consent
- **NFR-19:** Local workout data encrypted at rest (device encryption)
- **NFR-20:** Privacy policy link in settings

---

## 5. User Interface Guidelines

### 5.1 Navigation Structure
```
Bottom Tab Navigation (4 tabs):
├── Home (Dashboard)
│   ├── Start Workout button
│   ├── Today's Schedule card
│   ├── Recent PRs card
│   └── Quick Stats (weekly volume)
├── History
│   ├── Workout history list
│   └── Exercise detail screens
├── Schedule
│   ├── Calendar sync view
│   └── Workout event details
└── Profile
    ├── User info (from /auth/me)
    ├── Settings
    │   ├── Units (kg/lbs)
    │   ├── Notifications
    │   ├── Google Calendar sync days
    │   ├── Biometric auth toggle
    │   ├── Privacy policy
    │   └── Logout
    └── App version
```

### 5.2 Color Palette (Suggested)
- **Primary:** #4A90E2 (Blue) — CTAs, active states
- **Secondary:** #50C878 (Emerald Green) — Success, PRs
- **Accent:** #FF6B6B (Coral Red) — Warnings, declining trends
- **Background (Light):** #FFFFFF / #F5F5F5
- **Background (Dark):** #121212 / #1E1E1E
- **Text (Light):** #333333 / #666666
- **Text (Dark):** #FFFFFF / #B0B0B0

### 5.3 Typography
- **Headings:** SF Pro Display (iOS) / Roboto (Android) — Bold, 24-32pt
- **Body:** SF Pro Text (iOS) / Roboto (Android) — Regular, 16-18pt
- **Captions:** System font — Medium, 12-14pt

### 5.4 Component Library
Use platform-native components where possible:
- iOS: UIKit / SwiftUI standard components
- Android: Material Design 3 components
- Cross-platform (if React Native): React Native Paper or NativeBase

---

## 6. Technical Architecture

### 6.1 Recommended Tech Stack

#### **Option A: React Native (Recommended)**
- **Framework:** React Native 0.73+
- **Language:** TypeScript
- **State Management:** Zustand or Redux Toolkit
- **Navigation:** React Navigation 6
- **HTTP Client:** Axios with interceptors for token refresh
- **Storage:** AsyncStorage + react-native-keychain (tokens)
- **Charts:** react-native-chart-kit or Victory Native
- **Forms:** React Hook Form + Zod validation
- **Build System:** EAS (Expo Application Services) or native builds

**Pros:** Single codebase, fast iteration, large community, web reuse potential
**Cons:** Bridge overhead, larger app size

#### **Option B: Native (Swift + Kotlin)**
- **iOS:** Swift 5.9, SwiftUI, Combine
- **Android:** Kotlin 1.9, Jetpack Compose, Coroutines
- **Networking:** URLSession (iOS), Retrofit (Android)
- **Storage:** Keychain (iOS), EncryptedSharedPreferences (Android)
- **Charts:** Charts library (iOS), MPAndroidChart (Android)

**Pros:** Best performance, full platform feature access, native UX
**Cons:** 2x development cost, separate codebases

### 6.2 Architecture Pattern
- **MVVM (Model-View-ViewModel)** for separation of concerns
- **Repository Pattern** for data layer abstraction
- **Clean Architecture** layers:
  - **Presentation:** UI components, ViewModels
  - **Domain:** Business logic, use cases
  - **Data:** API client, local database, repositories

### 6.3 Key Modules

```
src/
├── api/
│   ├── client.ts              # Axios instance with interceptors
│   ├── auth.api.ts            # /auth/* endpoints
│   ├── workout.api.ts         # /workout/* endpoints
│   └── models.ts              # TypeScript types from backend schemas
├── stores/
│   ├── auth.store.ts          # User auth state, token management
│   ├── workout.store.ts       # Current session state
│   └── history.store.ts       # Cached workout history
├── screens/
│   ├── Auth/
│   │   ├── LoginScreen.tsx
│   │   └── RegisterScreen.tsx
│   ├── Home/
│   │   └── HomeScreen.tsx
│   ├── Workout/
│   │   ├── WorkoutSessionScreen.tsx
│   │   ├── ExercisePickerScreen.tsx
│   │   └── SessionSummaryScreen.tsx
│   ├── History/
│   │   ├── HistoryListScreen.tsx
│   │   └── ExerciseDetailScreen.tsx
│   ├── Schedule/
│   │   └── ScheduleScreen.tsx
│   └── Profile/
│       ├── ProfileScreen.tsx
│       └── SettingsScreen.tsx
├── components/
│   ├── ExerciseCard.tsx
│   ├── ProgressChart.tsx
│   ├── PRBadge.tsx
│   └── WeightInput.tsx
├── hooks/
│   ├── useAuth.ts
│   ├── useWorkoutSession.ts
│   └── useWorkoutHistory.ts
├── utils/
│   ├── tokenManager.ts        # Secure token storage/retrieval
│   ├── unitConverter.ts       # kg ↔ lbs
│   └── dateFormatter.ts
└── constants/
    ├── exercises.ts           # Pre-defined exercise library
    └── config.ts              # API base URL, timeouts
```

### 6.4 State Management Strategy

#### **Auth Store**
```typescript
interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, email: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<void>;
}
```

#### **Workout Session Store**
```typescript
interface WorkoutSessionState {
  isActive: boolean;
  startTime: Date | null;
  metadata: SessionMetadata;
  exercises: WorkoutEntry[];
  addExercise: (exercise: WorkoutEntry) => void;
  removeExercise: (index: number) => void;
  updateMetadata: (metadata: Partial<SessionMetadata>) => void;
  completeSession: () => Promise<WorkoutLogResponse>;
  cancelSession: () => void;
}
```

---

## 7. API Integration Details

### 7.1 Token Refresh Flow
```typescript
// Axios interceptor example
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const newAccessToken = await refreshAccessToken();
      originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
      return axios(originalRequest);
    }
    return Promise.reject(error);
  }
);
```

### 7.2 Error Handling Strategy
| HTTP Status | User-Facing Message | Action |
|-------------|---------------------|--------|
| 400 | "Invalid input. Please check your data." | Show inline validation errors |
| 401 | "Session expired. Please log in again." | Redirect to login, clear tokens |
| 403 | "You don't have permission to do that." | Show error toast |
| 404 | "Data not found." | Show empty state |
| 429 | "Too many requests. Please wait." | Show retry countdown |
| 500/503 | "Server error. Please try again later." | Show retry button |
| Network Error | "No internet connection." | Show offline banner |

### 7.3 Caching Strategy
- **User profile:** Cache 24 hours, refresh on app launch
- **Workout history:** Cache last 90 days, refresh on pull-to-refresh
- **Schedule:** Cache 7 days, refresh every 6 hours or manual sync
- **Exercise progress:** Cache per exercise, refresh when viewing detail screen
- **Exercise library:** Bundled with app, never fetch from API

---

## 8. Testing Requirements

### 8.1 Unit Tests
- API client methods (mock responses)
- Unit conversion utilities (kg ↔ lbs)
- 1RM calculation (Epley formula)
- Date formatters
- Form validation logic

### 8.2 Integration Tests
- Login/register flows
- Workout logging end-to-end
- Token refresh on 401
- Offline mode sync queue

### 8.3 UI Tests (E2E)
- Complete workout logging flow (login → start → add exercises → complete)
- View exercise progress
- Calendar sync
- Settings changes persist

### 8.4 Manual Testing Checklist
- [ ] Test on physical iOS device (iPhone 12 minimum)
- [ ] Test on physical Android device (Samsung Galaxy S21 minimum)
- [ ] Test with slow network (throttled to 3G)
- [ ] Test with no network (airplane mode)
- [ ] Test with VoiceOver enabled (iOS)
- [ ] Test with TalkBack enabled (Android)
- [ ] Test dark mode switching
- [ ] Test with Dynamic Type at largest size (iOS)
- [ ] Test app backgrounding mid-workout (session persists)
- [ ] Test on tablet layouts

---

## 9. Deployment & Release

### 9.1 Environment Configuration
| Environment | Base URL | Purpose |
|-------------|----------|---------|
| Development | `http://localhost:8000` | Local backend testing |
| Staging | `https://staging-api.fitness-ai.com` | QA testing |
| Production | `https://api.fitness-ai.com` | Live users |

### 9.2 App Store Requirements

#### **iOS (App Store Connect)**
- Bundle ID: `com.fitnessai.mobile`
- Minimum iOS version: 15.0
- Privacy Nutrition Labels:
  - Data Collected: Name, email, workout data
  - Data Linked to User: Yes
  - Data Used to Track: No
- Screenshots required: 6.5" iPhone, 12.9" iPad
- App category: Health & Fitness

#### **Android (Google Play Console)**
- Package name: `com.fitnessai.mobile`
- Minimum SDK: 26 (Android 8.0)
- Target SDK: 34 (Android 14)
- Permissions:
  - `android.permission.INTERNET` (required)
  - `android.permission.USE_BIOMETRIC` (optional, for biometric auth)
  - `android.permission.POST_NOTIFICATIONS` (optional, for push notifications)
- Feature graphic: 1024 x 500 px
- Screenshots: Phone + 7" tablet + 10" tablet

### 9.3 Release Checklist
- [ ] Backend API accessible and healthy (`/health` returns 200)
- [ ] JWT token flow tested (register, login, refresh)
- [ ] Google OAuth credentials configured (if using OAuth flow)
- [ ] Privacy policy hosted and linked in app
- [ ] App icons prepared (iOS 1024x1024, Android adaptive icon)
- [ ] App store descriptions written (English minimum)
- [ ] Beta testing via TestFlight (iOS) / Internal Testing (Android)
- [ ] Crash reporting configured (Firebase Crashlytics or Sentry)
- [ ] Analytics configured (optional, with user consent)

---

## 10. Success Metrics (KPIs)

### 10.1 Adoption Metrics
- **Target:** 1,000 registered users in first 3 months
- **Target:** 60% DAU/MAU ratio (daily active users / monthly active users)
- **Target:** 70% user retention after 7 days

### 10.2 Engagement Metrics
- **Target:** Average 3 workouts logged per user per week
- **Target:** 80% of started workouts completed (not abandoned mid-session)
- **Target:** Average session duration: 45-60 minutes

### 10.3 Technical Metrics
- **Target:** < 1% crash rate
- **Target:** Average API response time < 500ms (p95)
- **Target:** App size < 50MB (iOS), < 30MB (Android)

### 10.4 User Satisfaction
- **Target:** 4.5+ star rating on App Store and Google Play
- **Target:** < 5% negative reviews mentioning bugs
- **Target:** NPS (Net Promoter Score) > 50

---

## 11. Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Google API quota limits exceeded | High | Low | Implement caching, batch requests, upgrade quota if needed |
| Backend API downtime | High | Medium | Offline mode, local caching, queue failed requests |
| JWT token theft (man-in-the-middle) | Critical | Low | Enforce HTTPS, certificate pinning, short token expiry |
| Large media uploads (Phase 3 videos) | Medium | Medium | Compress videos client-side, implement upload resume |
| Cross-platform UI inconsistencies | Medium | High | Comprehensive design system, platform-specific components |
| Poor network performance in gyms | High | High | Aggressive caching, offline mode, optimistic UI updates |

---

## 12. Timeline Estimate

### Phase 1 (MVP) — 12-16 weeks
| Week | Milestone |
|------|-----------|
| 1-2 | Project setup, API client, authentication flow |
| 3-4 | Workout logging UI + API integration |
| 5-6 | History list + Exercise detail screens |
| 7-8 | Google Calendar sync + Schedule screen |
| 9-10 | Session metadata, exercise library, search |
| 11-12 | Progress charts, analytics screens |
| 13-14 | Polish, dark mode, accessibility |
| 15-16 | Testing, bug fixes, TestFlight/Internal Testing beta |

### Phase 2 (Enhanced) — 6-8 weeks
| Week | Milestone |
|------|-----------|
| 1-2 | Offline mode + sync queue |
| 3-4 | Rest timer, plate calculator |
| 5-6 | Workout templates, push notifications |
| 7-8 | Testing, beta feedback iteration |

### Phase 3 (AI Features) — 8-10 weeks
| Week | Milestone |
|------|-----------|
| 1-3 | Video upload + form analysis integration |
| 4-6 | LSTM prediction integration |
| 7-8 | UI polish for AI features |
| 9-10 | Testing, production release |

---

## 13. Appendix

### 13.1 Glossary
- **RPE (Rate of Perceived Exertion):** Subjective scale 1-10 measuring exercise difficulty
- **1RM (One-Rep Max):** Maximum weight that can be lifted for one repetition
- **Volume:** Total work done (sets × reps × weight)
- **PR (Personal Record):** Best performance achieved for an exercise
- **JWT (JSON Web Token):** Authentication token standard
- **Epley Formula:** 1RM = weight × (1 + reps / 30)

### 13.2 References
- Backend API documentation: `https://api.fitness-ai.com/docs`
- Swagger spec: `https://api.fitness-ai.com/openapi.json`
- Backend GitHub: (link to repository)
- Design mockups: (link to Figma/Sketch)

### 13.3 Open Questions
1. **Multi-language support:** Should Phase 1 include internationalization structure?
   - **Decision:** Yes, structure for i18n but English-only content initially
2. **Social features:** Should users be able to share workouts or compete with friends?
   - **Decision:** Deferred to Phase 4
3. **Wearable integration:** Apple Watch / Wear OS support?
   - **Decision:** Deferred to Phase 3 (after core mobile is stable)
4. **Premium tier:** Will there be paid features (e.g., advanced analytics)?
   - **Decision:** TBD by business team, app should support feature flags

---

## 14. Approval & Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Owner | __________ | __________ | __________ |
| Backend Lead | __________ | __________ | __________ |
| Mobile Lead | __________ | __________ | __________ |
| QA Lead | __________ | __________ | __________ |
| Stakeholder | __________ | __________ | __________ |

---

**Document Version Control:**
- v1.0 (2026-09-03): Initial requirements based on backend Phase 1 API
- v1.1 (TBD): Updated after design review
- v1.2 (TBD): Updated after technical spike

**Contact:**
- Product questions: [product@fitness-ai.com](mailto:product@fitness-ai.com)
- Technical questions: [dev@fitness-ai.com](mailto:dev@fitness-ai.com)
