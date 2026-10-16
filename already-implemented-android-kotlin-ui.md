# Fitness AI — Comprehensive Android Mobile Application Guide

A modern, high-performance Android fitness tracking and intelligent coaching application built with **Kotlin 2.2.10**, **Jetpack Compose (Material Design 3)**, and **Supabase PostgreSQL**.

Designed for real-time gym workout tracking, per-set custom rep & weight progression, Google Calendar schedule synchronization, and AI-powered performance analytics.

---

## 📱 Detailed Screen-by-Screen Walkthrough

### 1. Dashboard Screen (`DashboardScreen.kt`)
The primary hub displaying real-time workout stats, upcoming schedules, and recent personal records:
- **Hero Header**: Displays a personalized welcome message (*e.g., "WELCOME BACK, GymAthlete"*), current user profile avatar, and a primary **"Start Workout Now"** call-to-action button.
- **Live Stats Tiles (`StatTile`)**:
  - **Total Volume**: Sums all-time volume across all completed sessions in kilograms (`kg`).
  - **Sessions**: Counts unique completed workout days.
  - **Recent PRs**: Displays the total count of personal records achieved.
- **Upcoming Schedule Strip**: Horizontally scrollable preview of scheduled workouts (from Supabase or Google Calendar) showing workout duration, exercise type, location, and warm-up preview. Includes a **"View All"** button to jump to the Schedule screen.
- **Top Personal Records Showcase**: Cards highlighting top all-time records (*e.g., Bench Press, Squat, Deadlift*) computed dynamically from live user data with **`PRBadge`** tags.
- **Last Completed Session Card**: Displays the date, exercise details, sets, reps, volume, and session vitals (*Mood, Energy, Sleep Quality ratings*).

---

### 2. Log Workout Screen (`LogWorkoutScreen.kt`)
The core workout tracker supporting both single-exercise quick logging and multi-exercise session batch building:
- **Log Exercise Entry Form (Top Direct Input)**:
  - **Popular Lifts Filter Chips**: Quick-fill chips (*Bench Press, Squat, Deadlift, Overhead Press, Barbell Row, Pull-ups, Dips, Leg Press*) that auto-fill exercise defaults.
  - **Exercise Name Field with `🔍` Search Button**: Editable text field with an embedded search icon button `🔍` to launch the **Exercise Library Picker Popup** instantly.
  - **Target Muscle Group Selector**: Filter chips (*Chest, Back, Legs, Shoulders, Arms, Core, Full Body*) allowing explicit assignment of muscle groups for custom exercises.
  - **Live Computed Header**: Displays live **Estimated Volume** ($\sum \text{reps} \times \text{weight}$) and **Epley Estimated 1RM** ($W \times (1 + R / 30)$).
  - **Individual Per-Set Breakdown Table**:
    - **Set Rows (*Set 1, Set 2, Set 3, etc.*)**: Each set row has its own dedicated controls.
    - **Reps Stepper**: `-` and `+` buttons to adjust rep counts.
    - **Directly Editable Weight Box**: Numeric text input field allowing direct typing of any custom weight (*e.g. 52.5 kg, 67.5 kg, 122.5 kg*) paired with `-2.5` / `+2.5` steppers for quick adjustments.
    - **Row Deletion (`[X]`)**: Button to remove specific set rows.
    - **`+ Add Another Set` Button**: One-tap button to append new set rows dynamically.
  - **Rate of Perceived Exertion (RPE 1.0–10.0)**: Interactive slider with dynamic color indicator.
  - **Exercise Notes Input Field**: Text box for recording form notes or feel.
  - **Dual Action Buttons**:
    - **"Log Exercise"**: Saves the single exercise and all individual set rows directly to Supabase (`workout_logs` & `workout_sets`).
    - **"+ Batch Builder"**: Adds the exercise with its per-set breakdown to the active session builder.
- **Active Session Builder Section**:
  - Displays all staged exercises for the current workout session.
  - **Session Check-in Metadata Card**: Sliders/steppers for Mood (1–10), Energy (1–10), and Sleep Quality (1–10).
  - **`ExerciseEntryCard` Items**: Expandable cards for each staged exercise featuring full per-set editing, `🔍` search button, and deletion.
  - **"Save Full Workout Session" Button**: Submits the complete multi-exercise session and all individual set rows to Supabase in a single batch.
- **Logged Exercises Feed**: Chronological list of recently logged exercises with instant delete controls.

---

### 3. History Screen (`HistoryScreen.kt`)
Comprehensive chronological record of all logged training sessions:
- **Search & Filter Bar (`history_search_input`)**: Filter history by exercise name in real-time.
- **Date Range Filters**: Filter by time windows (*7 Days, 30 Days, 90 Days, All Time*).
- **Muscle Group Category Chips**: Filter by targeted muscle group (*Chest, Back, Legs, Shoulders, Arms, Core, Full Body*).
- **One-Tap "Export CSV" Button**: Generates and displays a Google Sheets / Excel compatible CSV modal with copy-to-clipboard functionality.
- **Interactive Session Cards**:
  - Displays workout date, exercise type badge, RPE indicator, exercise name, total sets, reps, weight, total volume, and estimated 1RM.
  - **Collapsible Per-Set Rep Breakdown**: Tapping any history card expands an in-depth table showing every individual set (*Set 1: 12 reps @ 50.0 kg, Set 2: 10 reps @ 60.0 kg, Set 3: 5 reps @ 75.0 kg*).
  - Shows recorded notes, vitals (*Mood, Energy, Sleep*), and verified form scores.
  - Includes a **"View Progress Chart"** button to jump to performance analytics for that lift.

---

### 4. Progress & Analytics Screen (`ProgressScreen.kt`)
Deep-dive performance analytics and strength regression tracking:
- **Exercise Selector Chips**: Scrollable row of all logged exercises to switch analytics focus.
- **Time Window Chips**: Toggle between *Last 30 Days*, *Last 90 Days*, and *Full Year*.
- **Analytical Stat Tiles**:
  - **Max Weight**: All-time maximum weight lifted (`kg`).
  - **Avg Weight**: Average weight lifted per session (`kg`).
  - **Total Sessions**: Count of logged sessions for the selected exercise.
  - **Max Volume**: Peak single-session volume achieved (`kg`).
- **Linear Regression Trend Card**: Displays progression direction (*Improving*, *Maintaining*, *Declining*), calculates strength gain slope (`kg/session`), and projects target weight 7 sessions ahead.
- **Custom Canvas Line Chart (`ProgressLineChart`)**: Renders actual historical progression points alongside a dashed neural projection line.
- **Personal Records Showcase**: Highlights Weight PRs, Volume PRs, and 1RM PRs with **`PRBadge`** tags.
- **Logged Sessions Feed with Collapsible Set Breakdown**: Displays past sessions for the selected exercise with expandable per-set rep & weight breakdown tables.

---

### 5. Calendar & Schedule Screen (`ScheduleScreen.kt`)
Workout scheduling and Google Calendar integration hub:
- **Header Controls**: Window selection chips (*7 Days, 14 Days, 30 Days*) and a **"Sync Google Calendar Now"** button (validates `google_credentials.json`).
- **"Schedule Workout" Action Button & Modal**:
  - Modal allowing users to create custom planned workouts with Title, Gym/Location, Duration, and Notes.
  - Custom scheduled workouts sync directly to the Supabase `calendar_events` table.
- **Scheduled Event Cards**:
  - Displays date/time, workout type badge, duration, title, and location.
  - **AI Warm-up Routine Box**: Lists suggested warm-up drills, warm-up duration, and focus muscle tags.
  - **"Start This Workout" Button**: Prefills the Log Workout screen with the scheduled exercise details.

---

### 6. AI Intelligence Labs Screen (`AiLabsScreen.kt`)
Advanced machine learning and computer vision analytics:
- **LSTM Strength Predictions**: Estimates next-session target weight, reps, RPE, and confidence score.
- **Computer Vision Form Kinematics**: Displays pose joint angle assessments, form scores (0–10), range of motion percentages, and coaching feedback.

---

### 7. Profile & Account Screen (`ProfileScreen.kt`)
User account, authentication, and system preferences:
- **User Profile Card**: Displays avatar icon, username, email address, and authentication status badge (*AUTHENTICATED ATHLETE* vs *GUEST ATHLETE*).
- **Supabase Account & Authentication**:
  - **Logged-In View**: Displays signed-in email address and **"Sign Out"** button.
  - **Sign In / Sign Up Form**: Tabbed interface for email/password authentication with validation banners.
  - **Native Google Sign-In ("Continue with Google")**: Uses Android Credential Manager API (`androidx.credentials`) to display an in-app bottom sheet for 1-second Google authentication.
- **Preferences & System**:
  - **Measurement Units**: Toggle between Metric (`kg`) and Imperial (`lbs`).
  - **Google Calendar Integration**: Active connection status.

---

## 🏗️ Complete Entity Structures

### 1. `WorkoutSetEntry`
Represents an individual set within an exercise:
```kotlin
@Serializable
data class WorkoutSetEntry(
    @SerializedName("id") @SerialName("id") val id: String = UUID.randomUUID().toString(),
    @SerializedName("log_id") @SerialName("log_id") val logId: Long? = null,
    @SerializedName("exercise") @SerialName("exercise") val exercise: String = "",
    @SerializedName("set_number") @SerialName("set_number") val setNumber: Int = 1,
    @SerializedName("reps") @SerialName("reps") val reps: Int = 10,
    @SerializedName("weight_kg") @SerialName("weight_kg") val weightKg: Float = 60.0f,
    @SerializedName("rpe") @SerialName("rpe") val rpe: Float = 7.5f,
    @SerializedName("user_id") @SerialName("user_id") val userId: String = "user-athlete-1"
)
```

### 2. `WorkoutEntry`
Represents a staged exercise entry in the session builder:
```kotlin
@Serializable
data class WorkoutEntry(
    val id: String = UUID.randomUUID().toString(),
    @SerializedName("exercise") @SerialName("exercise") val exercise: String = "",
    @SerializedName("sets") @SerialName("sets") val sets: Int = 3,
    @SerializedName("reps") @SerialName("reps") val reps: Int = 10,
    @SerializedName("weight_kg") @SerialName("weight_kg") val weightKg: Float = 60.0f,
    @SerializedName("rpe") @SerialName("rpe") val rpe: Float = 7.0f,
    @SerializedName("exercise_type") @SerialName("exercise_type") val exerciseType: ExerciseType = ExerciseType.STRENGTH,
    @SerializedName("muscle_group") @SerialName("muscle_group") val muscleGroup: MuscleGroup = MuscleGroup.CHEST,
    @SerializedName("notes") @SerialName("notes") val notes: String = "",
    @SerializedName("form_score") @SerialName("form_score") val formScore: Int? = null,
    @SerializedName("range_of_motion") @SerialName("range_of_motion") val rangeOfMotion: Int? = null,
    @SerializedName("device_data") @SerialName("device_data") val deviceData: String = "",
    @SerializedName("sets_list") @SerialName("sets_list") val setsList: List<WorkoutSetEntry> = emptyList()
) {
    val volume: Float
        get() = if (setsList.isNotEmpty()) setsList.sumOf { (it.reps * it.weightKg).toDouble() }.toFloat() else sets * reps * weightKg

    val estimated1RM: Float
        get() {
            if (setsList.isNotEmpty()) {
                val maxSet = setsList.maxByOrNull { it.weightKg * (1f + it.reps / 30f) }
                return maxSet?.let { it.weightKg * (1f + it.reps / 30f) } ?: 0f
            }
            return if (reps > 0) weightKg * (1f + reps / 30f) else weightKg
        }
}
```

### 3. `HistoryRecord`
Represents a logged workout history record stored in Supabase:
```kotlin
@Serializable
data class HistoryRecord(
    @SerializedName("id") @SerialName("id") val id: String = UUID.randomUUID().toString(),
    @SerializedName("date") @SerialName("date") val date: String,
    @SerializedName("user_id") @SerialName("user_id") val userId: String,
    @SerializedName("exercise") @SerialName("exercise") val exercise: String,
    @SerializedName("exercise_type") @SerialName("exercise_type") val exerciseType: String,
    @SerializedName("muscle_group") @SerialName("muscle_group") val muscleGroup: String,
    @SerializedName("sets") @SerialName("sets") val sets: Int,
    @SerializedName("reps") @SerialName("reps") val reps: Int,
    @SerializedName("weight_kg") @SerialName("weight_kg") val weightKg: Float,
    @SerializedName("rpe") @SerialName("rpe") val rpe: Float,
    @SerializedName("volume") @SerialName("volume") val volume: Float,
    @SerializedName("one_rm") @SerialName("one_rm") val oneRm: Float,
    @SerializedName("mood") @SerialName("mood") val mood: Int,
    @SerializedName("energy") @SerialName("energy") val energy: Int,
    @SerializedName("sleep_quality") @SerialName("sleep_quality") val sleepQuality: Int,
    @SerializedName("notes") @SerialName("notes") val notes: String = "",
    @SerializedName("form_score") @SerialName("form_score") val formScore: String = "",
    @SerializedName("range_of_motion") @SerialName("range_of_motion") val rangeOfMotion: String = "",
    @SerializedName("device_data") @SerialName("device_data") val deviceData: String = "",
    @SerializedName("timestamp") @SerialName("timestamp") val timestamp: String = "",
    @SerializedName("sets_list") @SerialName("sets_list") val setsList: List<WorkoutSetEntry> = emptyList()
)
```

### 4. `UserProfile`
Represents user profile information:
```kotlin
@Serializable
data class UserProfile(
    @SerializedName("user_id") @SerialName("user_id") val userId: String = "user-demo-uuid",
    @SerializedName("username") @SerialName("username") val username: String = "GymAthlete",
    @SerializedName("email") @SerialName("email") val email: String = "athlete@fitness-ai.com"
)
```

### 5. `ExerciseDef`
Represents an exercise definition in the Exercise Library:
```kotlin
@Serializable
data class ExerciseDef(
    @SerialName("id") val id: String = "",
    @SerialName("name") val name: String = "",
    @SerialName("muscle_group") val muscleGroupStr: String = "chest",
    @SerialName("exercise_type") val exerciseTypeStr: String = "strength",
    @SerialName("default_weight_kg") val defaultWeightKg: Float = 50f,
    @SerialName("default_sets") val defaultSets: Int = 3,
    @SerialName("default_reps") val defaultReps: Int = 10
)
```

### 6. `CalendarEvent` & `CalendarAiInsights`
Represents scheduled workout plans and AI warm-up guidance:
```kotlin
@Serializable
data class CalendarAiInsights(
    @SerializedName("focus_muscles") @SerialName("focus_muscles") val focusMuscles: List<String> = emptyList(),
    @SerializedName("suggested_warmup") @SerialName("suggested_warmup") val suggestedWarmup: List<String> = emptyList(),
    @SerializedName("warm_up_time_min") @SerialName("warm_up_time_min") val warmUpTimeMin: Int = 10,
    @SerializedName("estimated_duration_min") @SerialName("estimated_duration_min") val estimatedDurationMin: Int = 60,
    @SerializedName("type") @SerialName("type") val type: String = "strength"
)

@Serializable
data class CalendarEvent(
    @SerializedName("id") @SerialName("id") val id: String = UUID.randomUUID().toString(),
    @SerializedName("title") @SerialName("title") val title: String,
    @SerializedName("start") @SerialName("start") val start: String,
    @SerializedName("end") @SerialName("end") val end: String,
    @SerializedName("description") @SerialName("description") val description: String = "",
    @SerializedName("location") @SerialName("location") val location: String = "",
    @SerializedName("type") @SerialName("type") val type: String = "strength",
    @SerializedName("estimated_duration_min") @SerialName("estimated_duration_min") val estimatedDurationMin: Int = 60,
    @SerializedName("estimated_volume") @SerialName("estimated_volume") val estimatedVolume: Int = 2400,
    @SerializedName("ai_insights") @SerialName("ai_insights") val aiInsights: CalendarAiInsights = CalendarAiInsights()
)
```

### 7. `WorkoutLogEntity` (Room / Local SQLite Entity)
Local database table mapping for workout logs:
```kotlin
@Entity(tableName = "workout_logs")
@Serializable
data class WorkoutLogEntity(
    @PrimaryKey(autoGenerate = true)
    @SerialName("id") val id: Long = 0,
    @ColumnInfo(name = "user_id") @SerialName("user_id") val userId: String = "user-athlete-1",
    @ColumnInfo(name = "exercise") @SerialName("exercise") val exercise: String,
    @ColumnInfo(name = "sets") @SerialName("sets") val sets: Int,
    @ColumnInfo(name = "reps") @SerialName("reps") val reps: Int,
    @ColumnInfo(name = "weight_kg") @SerialName("weight_kg") val weightKg: Float,
    @ColumnInfo(name = "rpe") @SerialName("rpe") val rpe: Float = 7.5f,
    @ColumnInfo(name = "muscle_group") @SerialName("muscle_group") val muscleGroup: String = "Chest",
    @ColumnInfo(name = "exercise_type") @SerialName("exercise_type") val exerciseType: String = "strength",
    @ColumnInfo(name = "notes") @SerialName("notes") val notes: String = "",
    @ColumnInfo(name = "mood") @SerialName("mood") val mood: Int = 8,
    @ColumnInfo(name = "energy") @SerialName("energy") val energy: Int = 8,
    @ColumnInfo(name = "sleep_quality") @SerialName("sleep_quality") val sleepQuality: Int = 8,
    @ColumnInfo(name = "timestamp") @SerialName("timestamp") val timestamp: Long = System.currentTimeMillis()
)
```

---

## 🗄️ Supabase PostgreSQL Schema (`supabase_schema.sql`)

```sql
-- 1. TODOS TABLE
CREATE TABLE IF NOT EXISTS public.todos (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. HISTORY RECORDS TABLE
CREATE TABLE IF NOT EXISTS public.history_records (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'user-athlete-1',
    exercise TEXT NOT NULL,
    exercise_type TEXT DEFAULT 'strength',
    muscle_group TEXT DEFAULT 'chest',
    sets INTEGER NOT NULL DEFAULT 3,
    reps INTEGER NOT NULL DEFAULT 10,
    weight_kg NUMERIC NOT NULL DEFAULT 60.0,
    rpe NUMERIC DEFAULT 7.5,
    volume NUMERIC DEFAULT 0.0,
    one_rm NUMERIC DEFAULT 0.0,
    mood INTEGER DEFAULT 8,
    energy INTEGER DEFAULT 8,
    sleep_quality INTEGER DEFAULT 8,
    notes TEXT DEFAULT '',
    form_score TEXT DEFAULT '',
    range_of_motion TEXT DEFAULT '',
    device_data TEXT DEFAULT '',
    timestamp TEXT DEFAULT ''
);

-- 3. CALENDAR EVENTS TABLE
CREATE TABLE IF NOT EXISTS public.calendar_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    description TEXT DEFAULT '',
    location TEXT DEFAULT '',
    type TEXT DEFAULT 'strength',
    duration_min INTEGER DEFAULT 60,
    est_volume INTEGER DEFAULT 2400,
    insights_json JSONB DEFAULT '{}'::jsonb
);

-- 4. WORKOUT LOGS TABLE
CREATE TABLE IF NOT EXISTS public.workout_logs (
    id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'user-athlete-1',
    exercise TEXT NOT NULL,
    sets INTEGER NOT NULL DEFAULT 3,
    reps INTEGER NOT NULL DEFAULT 10,
    weight_kg NUMERIC NOT NULL DEFAULT 60.0,
    rpe NUMERIC DEFAULT 7.5,
    muscle_group TEXT DEFAULT 'Chest',
    exercise_type TEXT DEFAULT 'strength',
    notes TEXT DEFAULT '',
    volume NUMERIC DEFAULT 0.0,
    one_rm NUMERIC DEFAULT 0.0,
    date TEXT DEFAULT '',
    timestamp BIGINT DEFAULT 0,
    mood INTEGER DEFAULT 8,
    energy INTEGER DEFAULT 8,
    sleep_quality INTEGER DEFAULT 8,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. USER PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.user_profiles (
    user_id TEXT PRIMARY KEY DEFAULT 'user-demo-uuid',
    username TEXT NOT NULL DEFAULT 'GymAthlete',
    email TEXT NOT NULL DEFAULT 'athlete@fitness-ai.com',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. MASTER EXERCISES TABLE
CREATE TABLE IF NOT EXISTS public.exercises (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    muscle_group TEXT NOT NULL,
    exercise_type TEXT NOT NULL DEFAULT 'strength',
    default_weight_kg NUMERIC DEFAULT 50.0,
    default_sets INTEGER DEFAULT 3,
    default_reps INTEGER DEFAULT 10
);

-- 7. WORKOUT SETS TABLE (Detailed per-set tracking)
CREATE TABLE IF NOT EXISTS public.workout_sets (
    id TEXT PRIMARY KEY,
    log_id BIGINT,
    exercise TEXT NOT NULL,
    set_number INTEGER NOT NULL DEFAULT 1,
    reps INTEGER NOT NULL DEFAULT 10,
    weight_kg NUMERIC NOT NULL DEFAULT 60.0,
    rpe NUMERIC DEFAULT 7.5,
    user_id TEXT NOT NULL DEFAULT 'user-athlete-1',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🛠️ Tech Stack & Dependencies

- **Kotlin**: 2.2.10
- **Android Target SDK**: 36 (minSdk 26)
- **UI Framework**: Jetpack Compose (Material Design 3)
- **Supabase Stack**: `io.github.jan-tennert.supabase` v3.1.0 (`postgrest-kt` & `auth-kt`)
- **Android Credentials API**: `androidx.credentials` v1.5.0 & `com.google.android.libraries.identity.googleid` v1.1.1
- **Networking**: Ktor Client OkHttp v3.0.3 & OkHttp v4.12.0
- **Serialization**: `kotlinx-serialization-json` v1.8.0

---

## 📦 How to Build the App & Locate the APK

Run the Gradle assembly task:

```bash
gradle app:assembleDebug
```

The compiled Android `.apk` file is located at:
> **`app/build/outputs/apk/debug/app-debug.apk`**
