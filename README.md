# Fitness AI — Backend API

State-of-the-art AI fitness platform built on FastAPI + Python.
Phase 1: Google Calendar sync, Google Sheets workout logging, JWT auth.

---

## Project Structure

```
fitness_ai/
├── src/
│   ├── main.py                          # FastAPI app entry point
│   ├── core/
│   │   ├── config.py                    # Pydantic settings (reads .env)
│   │   ├── models/domain.py             # Domain models + Pydantic schemas
│   │   └── services/
│   │       ├── calendar.py              # Google Calendar integration
│   │       └── sheets.py               # Google Sheets integration
│   ├── api/
│   │   ├── middleware/auth.py           # JWT middleware
│   │   └── v1/routes/
│   │       ├── auth.py                  # /auth/token, /auth/refresh
│   │       └── workout.py               # /workout/* endpoints
│   ├── ai/                              # Phase 2+ (LSTM, pose, LLM)
│   ├── data/                            # Phase 2+ (repositories)
│   └── utils/logging.py
├── scripts/
│   └── init.sql                         # Postgres schema
├── credentials/                         # Google credentials (gitignored)
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Quickstart (Local Dev)

### 1. Clone and set up environment

```bash
python -m venv venv
source venv/bin/activate           # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Set up Google credentials

**Option A — Service Account (recommended for production)**

1. Go to [Google Cloud Console](https://console.cloud.google.com) → IAM & Admin → Service Accounts
2. Create a service account, download the JSON key
3. Save as `credentials/service_account.json`
4. Enable **Google Calendar API** and **Google Sheets API** in your project
5. Share your Google Sheet with the service account email (Editor role)
6. In `.env`: set `GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json`

**Option B — OAuth 2.0 (easiest for personal use)**

1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID → Desktop Application
3. Download the JSON, save as `credentials/google_oauth.json`
4. Enable **Google Calendar API** and **Google Sheets API**
5. First run will open a browser window for user consent; token is cached to `credentials/token.json`

### 3. Create your Google Sheet

1. Create a new Google Sheet at [sheets.google.com](https://sheets.google.com)
2. Copy the spreadsheet key from the URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_IS_YOUR_KEY`**`/edit`
3. Set `GOOGLE_SPREADSHEET_KEY=your-key` in `.env`

The service will auto-create the `WorkoutLog` worksheet with correct headers on first write.

### 4. Run the server

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Visit:
- **Swagger UI**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

---

## Docker (Full Stack)

```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials and keys

# Start Postgres + Redis + Backend
docker-compose up --build -d

# With ML worker (Phase 2+)
docker-compose --profile ml up -d

# Check logs
docker-compose logs -f backend
```

---

## API Reference & Test Commands

### Get an auth token

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "secret": "dev"}' | python3 -m json.tool
```

### Log a workout

```bash
TOKEN="your-access-token-here"

curl -s -X POST http://localhost:8000/api/v1/workout/log \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "alice",
    "entries": [
      {
        "exercise": "Bench Press",
        "sets": 4,
        "reps": 8,
        "weight_kg": 80,
        "rpe": 7.5,
        "exercise_type": "strength",
        "muscle_group": "chest"
      },
      {
        "exercise": "Overhead Press",
        "sets": 3,
        "reps": 10,
        "weight_kg": 50,
        "rpe": 7,
        "muscle_group": "shoulders"
      }
    ],
    "session_metadata": {
      "mood": 8,
      "energy": 7,
      "sleep_quality": 8
    }
  }' | python3 -m json.tool
```

### Sync Google Calendar

```bash
curl -s -X POST "http://localhost:8000/api/v1/workout/schedule/sync?days_ahead=7" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Get exercise progress

```bash
curl -s "http://localhost:8000/api/v1/workout/progress/Bench%20Press?days=90" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Get workout history

```bash
curl -s "http://localhost:8000/api/v1/workout/history?exercise=Bench%20Press&days=30" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## Phase Roadmap

| Phase | Status | What ships |
|-------|--------|------------|
| **1 — Scaffold + Google APIs** | ✅ Done | FastAPI, Calendar sync, Sheets logger, JWT auth |
| **2 — LSTM Predictor** | Next | Workout prediction (weight/reps/RPE) with confidence intervals |
| **3 — Pose Estimation** | Soon | Video upload → form analysis via MediaPipe + YOLOv8 |
| **4 — LLM Coach** | Soon | GPT-4 powered personalized coaching and progress narrative |
| **5 — Docker + ML Ops** | Soon | Production deploy, Celery workers, model training pipeline |

---

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | Path to service account JSON | Option A |
| `GOOGLE_CREDENTIALS_FILE` | Path to OAuth client JSON | Option B |
| `GOOGLE_SPREADSHEET_KEY` | Google Sheets spreadsheet key | ✅ |
| `GOOGLE_CALENDAR_ID` | Calendar ID (default: `primary`) | ✅ |
| `APP_SECRET_KEY` | JWT signing secret (use random 32-byte hex) | ✅ |
| `DATABASE_URL` | Postgres connection string | Phase 2+ |
| `REDIS_URL` | Redis connection string | Phase 2+ |
| `OPENAI_API_KEY` | OpenAI key for LLM coach | Phase 4 |

Generate a secure secret key:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```
