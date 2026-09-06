-- Enable pgvector for Phase 2 embeddings
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Users ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id   TEXT UNIQUE NOT NULL,   -- username or Google sub / auth provider UID
    email         TEXT,
    password_hash TEXT,                   -- bcrypt hash for username/password auth
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── Workout sessions ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workout_sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status      TEXT NOT NULL DEFAULT 'completed',
    total_volume FLOAT,
    mood        INT,
    energy      INT,
    sleep_quality INT,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Workout entries ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS workout_entries (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID REFERENCES workout_sessions(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    exercise        TEXT NOT NULL,
    exercise_type   TEXT NOT NULL DEFAULT 'strength',
    muscle_group    TEXT,
    sets            INT NOT NULL,
    reps            INT NOT NULL,
    weight_kg       FLOAT NOT NULL,
    rpe             FLOAT,
    volume          FLOAT GENERATED ALWAYS AS (sets * reps * weight_kg) STORED,
    one_rm          FLOAT,
    form_score      FLOAT,
    range_of_motion FLOAT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ── Model predictions cache (Phase 2) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    exercise    TEXT NOT NULL,
    predicted_weight FLOAT,
    predicted_reps   INT,
    predicted_rpe    FLOAT,
    confidence_lower FLOAT,
    confidence_upper FLOAT,
    model_version    TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── User embeddings (Phase 4 — LLM coach memory) ──────────────────────────────
CREATE TABLE IF NOT EXISTS user_embeddings (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(1536),          -- OpenAI text-embedding-3-small
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_entries_user_exercise ON workout_entries(user_id, exercise);
CREATE INDEX IF NOT EXISTS idx_entries_user_date ON workout_entries(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON workout_sessions(user_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_user_exercise ON predictions(user_id, exercise);

-- pgvector cosine similarity index (Phase 4)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector
    ON user_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
