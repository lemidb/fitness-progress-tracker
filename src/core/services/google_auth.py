"""
Shared Google credential helper.

Provides a single `get_google_credentials(scopes)` function used by
all services (Sheets, Calendar, …).  Credentials are loaded once and
reused across calls in the same process.

Auth priority:
  1. Service-account JSON  (set GOOGLE_SERVICE_ACCOUNT_FILE in .env)
  2. Per-user DB token     (google_tokens table, keyed by user_id UUID)
  3. Shared OAuth token    (credentials/token.json, written by `scripts/authorize_google.py`)
  4. Raise RuntimeError    (do NOT fall back to run_local_server — that blocks the server)

The token is refreshed automatically when expired.  For the per-user path,
the refreshed token is persisted back to the DB.  For the shared file path,
it is written back to credentials/token.json.

Run `python scripts/authorize_google.py` once (shared path) or direct users
to `GET /api/v1/auth/google` (per-user path) to obtain the initial token.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuthCredentials

from src.core.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Combined scopes for all Google services used by this app.
# A single token covers everything — no per-service mismatch.
ALL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def get_google_credentials() -> Credentials:
    """
    Return valid Google credentials for the server's own account
    (service-account or shared OAuth token from credentials/token.json).

    Use this in services that operate on a single set of Google resources
    (e.g. a shared spreadsheet owned by the app).  For per-user resources,
    call `get_user_google_credentials(user_id, session)` instead.

    Raises
    ------
    FileNotFoundError
        When neither a service-account file nor a token.json are present.
    RuntimeError
        When the token exists but is expired AND has no refresh token
        (re-run `scripts/authorize_google.py` in that case).
    """
    settings = get_settings()

    # ── 1. Service account (preferred for server deployments) ───────────────
    sa_file = settings.google_service_account_file
    if sa_file and Path(sa_file).exists():
        logger.info("Google auth: using service account → %s", sa_file)
        return service_account.Credentials.from_service_account_file(
            sa_file, scopes=ALL_SCOPES
        )

    # ── 2. Saved OAuth token ─────────────────────────────────────────────────
    token_path = Path(settings.google_token_file)
    if not token_path.exists():
        raise FileNotFoundError(
            f"Google OAuth token not found at '{token_path}'. "
            "Run `python scripts/authorize_google.py` once to generate it."
        )

    creds = OAuthCredentials.from_authorized_user_file(str(token_path), ALL_SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        logger.info("Google auth: token expired — refreshing …")
        creds.refresh(Request())
        # Persist the refreshed token so the next process start is instant.
        token_path.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Google auth: token refreshed and saved")
        return creds

    # Token is invalid and cannot be refreshed — user must re-authorise.
    raise RuntimeError(
        "Google OAuth token is invalid and cannot be refreshed. "
        "Run `python scripts/authorize_google.py` to re-authorise."
    )


async def get_user_google_credentials(
    user_id: str | uuid.UUID,
    session: "AsyncSession",
) -> OAuthCredentials:
    """
    Load and (if needed) refresh per-user Google OAuth credentials from the DB.

    Parameters
    ----------
    user_id:
        The internal UUID of the authenticated user.
    session:
        An open async SQLAlchemy session.

    Returns
    -------
    google.oauth2.credentials.Credentials
        A valid, possibly freshly refreshed credential object.

    Raises
    ------
    ValueError
        When the user has not yet connected their Google account.
    RuntimeError
        When the stored token is expired and cannot be refreshed
        (re-directs the user to `GET /api/v1/auth/google`).
    """
    from sqlalchemy import select

    from src.data.models.google_token import GoogleToken

    uid = uuid.UUID(str(user_id))

    result = await session.execute(
        select(GoogleToken).where(GoogleToken.user_id == uid)
    )
    row = result.scalar_one_or_none()

    if row is None:
        raise ValueError(
            f"User {uid} has not connected their Google account. "
            "Direct them to GET /api/v1/auth/google."
        )

    token_info = json.loads(row.token_json)
    creds = OAuthCredentials.from_authorized_user_info(token_info, ALL_SCOPES)

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        logger.info("Google auth: refreshing token for user=%s", uid)
        creds.refresh(Request())
        # Write the new token back so we don't refresh on every request.
        row.token_json = creds.to_json()
        await session.commit()
        logger.info("Google auth: token refreshed for user=%s", uid)
        return creds

    raise RuntimeError(
        f"Google token for user {uid} is expired and cannot be refreshed. "
        "Ask the user to re-connect via GET /api/v1/auth/google."
    )


async def save_user_google_credentials(
    user_id: str | uuid.UUID,
    creds: OAuthCredentials,
    google_email: str | None,
    session: "AsyncSession",
) -> None:
    """
    Upsert a user's Google OAuth credentials into the google_tokens table.

    Parameters
    ----------
    user_id:
        The internal UUID of the authenticated user.
    creds:
        A fully authorised credential object (with refresh_token present).
    google_email:
        The Google account email, for display/debugging (may be None).
    session:
        An open async SQLAlchemy session.
    """
    from sqlalchemy.dialects.postgresql import insert

    from src.data.models.google_token import GoogleToken

    uid = uuid.UUID(str(user_id))

    stmt = (
        insert(GoogleToken)
        .values(
            user_id=uid,
            token_json=creds.to_json(),
            google_email=google_email,
        )
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "token_json": creds.to_json(),
                "google_email": google_email,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    logger.info("Google auth: token saved for user=%s email=%s", uid, google_email)
