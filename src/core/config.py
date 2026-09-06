from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_secret_key: str = "change-me"
    app_debug: bool = True
    app_title: str = "Fitness AI API"
    app_version: str = "1.0.0"

    # ── Google ───────────────────────────────────────────────────────────────
    google_credentials_file: str = "credentials/google_oauth.json"
    google_token_file: str = "credentials/token.json"
    google_service_account_file: str = ""
    google_spreadsheet_key: str = ""
    google_worksheet_name: str = "WorkoutLog"
    google_calendar_id: str = "primary"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://admin:password@localhost:5432/fitness_ai"
    redis_url: str = "redis://localhost:6379/0"

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # ── AI ───────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    model_path: str = "models/"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def credentials_dir(self) -> Path:
        return Path(self.google_credentials_file).parent


@lru_cache
def get_settings() -> Settings:
    return Settings()
