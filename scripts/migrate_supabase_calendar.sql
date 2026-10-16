-- Calendar Phase 2 migration. Run after migrate_supabase_workouts.sql.
-- Legacy events have no trustworthy owner, so preserve them but remove API access.
BEGIN;

DO $$
BEGIN
    IF to_regclass('public.calendar_events') IS NOT NULL
       AND to_regclass('public.legacy_calendar_events') IS NULL
       AND NOT EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema = 'public'
             AND table_name = 'calendar_events'
             AND column_name = 'user_id'
             AND data_type = 'uuid'
       ) THEN
        ALTER TABLE public.calendar_events RENAME TO legacy_calendar_events;
    END IF;
END $$;

DO $$
DECLARE
    policy_record RECORD;
BEGIN
    IF to_regclass('public.legacy_calendar_events') IS NOT NULL THEN
        ALTER TABLE public.legacy_calendar_events ENABLE ROW LEVEL SECURITY;
        FOR policy_record IN
            SELECT policyname FROM pg_policies
            WHERE schemaname = 'public' AND tablename = 'legacy_calendar_events'
        LOOP
            EXECUTE format('DROP POLICY %I ON public.legacy_calendar_events', policy_record.policyname);
        END LOOP;
        REVOKE ALL ON TABLE public.legacy_calendar_events FROM anon, authenticated;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    location VARCHAR(500) NOT NULL DEFAULT '',
    exercise_type VARCHAR(32) NOT NULL DEFAULT 'strength'
        CHECK (exercise_type IN ('strength', 'cardio', 'flexibility', 'mixed')),
    estimated_duration_min INTEGER NOT NULL DEFAULT 60 CHECK (estimated_duration_min > 0),
    estimated_volume INTEGER NOT NULL DEFAULT 0 CHECK (estimated_volume >= 0),
    ai_insights JSONB NOT NULL DEFAULT '{}'::jsonb,
    source VARCHAR(16) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual', 'google')),
    provider_event_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_calendar_events_time_order CHECK (end_time > start_time),
    CONSTRAINT uq_calendar_events_user_provider_id UNIQUE (user_id, provider_event_id)
);

CREATE INDEX IF NOT EXISTS ix_calendar_events_user_id ON public.calendar_events(user_id);
CREATE INDEX IF NOT EXISTS ix_calendar_events_user_start_time
    ON public.calendar_events(user_id, start_time);

CREATE TABLE IF NOT EXISTS public.google_calendar_connections (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    is_connected BOOLEAN NOT NULL DEFAULT TRUE,
    account_email VARCHAR(320),
    scopes JSONB NOT NULL DEFAULT '[]'::jsonb,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ
);

ALTER TABLE public.calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.google_calendar_connections ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS calendar_events_owner_access ON public.calendar_events;
CREATE POLICY calendar_events_owner_access ON public.calendar_events
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));
DROP POLICY IF EXISTS google_calendar_connections_owner_access ON public.google_calendar_connections;
CREATE POLICY google_calendar_connections_owner_access ON public.google_calendar_connections
    FOR ALL TO authenticated
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

REVOKE ALL ON TABLE public.calendar_events, public.google_calendar_connections FROM anon, authenticated;
COMMIT;