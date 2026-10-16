from src.data.database import normalize_async_database_url


def test_normalize_supabase_pooler_url_for_asyncpg():
    url = normalize_async_database_url(
        "postgresql://user:password@aws-1.pooler.supabase.com:6543/postgres"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert url.query["ssl"] == "require"
    assert "statement_cache_size" not in url.query
    assert url.password == "password"


def test_normalize_local_postgres_url_without_supabase_options():
    url = normalize_async_database_url(
        "postgresql://user:password@localhost:5432/fitness_ai"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert "ssl" not in url.query
    assert "statement_cache_size" not in url.query
