"""
Google OAuth 2.0 routes for per-user account linking.

These endpoints let individual users connect their own Google account
so the server can read _their_ Calendar and _their_ Sheets on their behalf.

Flow
----
1.  User calls  GET  /api/v1/auth/google
    →  Server generates the Google consent-screen URL and returns it.
    →  Frontend redirects the user's browser to that URL.

2.  Google redirects to GOOGLE_OAUTH_REDIRECT_URI (must be registered
    in GCP Console → Credentials → OAuth client → Authorised redirect URIs).
    e.g.  http://localhost:8000/api/v1/auth/google/callback

3.  POST /api/v1/auth/google/callback
    Body: {"code": "<authorization_code_from_query_string>"}
    →  Server exchanges the code for tokens, stores them in `google_tokens`,
       and returns {"connected": true, "google_email": "..."}.

The caller must be authenticated (valid JWT) for both steps.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.middleware.auth import get_current_user
from src.core.config import get_settings
from src.core.services.google_auth import (
    ALL_SCOPES,
    save_user_google_credentials,
)
from src.data.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/google", tags=["google-oauth"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class GoogleAuthURL(BaseModel):
    auth_url: str
    message: str = (
        "Open auth_url in a browser, approve access, then POST the "
        "?code= query parameter to /api/v1/auth/google/callback"
    )


class GoogleCallbackPayload(BaseModel):
    code: str


class GoogleConnectedResponse(BaseModel):
    connected: bool
    google_email: str | None = None
    message: str = "Google account linked successfully."


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_flow() -> Flow:
    """Build a google_auth_oauthlib Flow from the app's OAuth client file."""
    settings = get_settings()
    redirect_uri = settings.google_oauth_redirect_uri

    flow = Flow.from_client_secrets_file(
        settings.google_credentials_file,
        scopes=ALL_SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def _fetch_google_email(creds) -> str | None:
    """
    Look up the Google account email for a freshly obtained credential.
    Returns None if the userinfo call fails (non-fatal).
    """
    try:
        service = build("oauth2", "v2", credentials=creds)
        info = service.userinfo().get().execute()
        return info.get("email")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch Google email after OAuth: %s", exc)
        return None


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("", response_model=GoogleAuthURL)
async def google_auth_url(
    current_user: Annotated[str, Depends(get_current_user)],
):
    """
    Generate the Google consent-screen URL for the requesting user.

    The frontend should redirect the user's browser to `auth_url`.
    After approval, Google redirects the browser to `GOOGLE_OAUTH_REDIRECT_URI`
    appending `?code=<authorization_code>`.  Collect that code and POST it to
    `/api/v1/auth/google/callback`.
    """
    flow = _make_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",   # required to get a refresh_token
        prompt="consent",        # force showing consent so refresh_token is always issued
        include_granted_scopes="true",
    )
    logger.info("Google auth URL generated for user=%s", current_user)
    return GoogleAuthURL(auth_url=auth_url)


@router.post("/callback", response_model=GoogleConnectedResponse)
async def google_callback(
    payload: GoogleCallbackPayload,
    current_user: Annotated[str, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Exchange the authorization code for tokens and persist them.

    After the user approves at the Google consent screen, Google appends
    `?code=<value>` to the redirect URI.  Pass that value here.
    """
    flow = _make_flow()

    try:
        flow.fetch_token(code=payload.code)
    except Exception as exc:
        logger.error("Google token exchange failed for user=%s: %s", current_user, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange Google authorization code: {exc}",
        ) from exc

    creds = flow.credentials

    if not creds.refresh_token:
        # This happens when the user has previously approved and Google skips
        # issuing a new refresh_token.  prompt="consent" above normally prevents
        # this, but handle it defensively.
        logger.warning(
            "No refresh_token in Google response for user=%s — "
            "user may need to revoke access at myaccount.google.com/permissions "
            "and re-connect.",
            current_user,
        )

    google_email = _fetch_google_email(creds)

    await save_user_google_credentials(
        user_id=current_user,
        creds=creds,
        google_email=google_email,
        session=session,
    )

    logger.info(
        "Google account linked for user=%s email=%s", current_user, google_email
    )
    return GoogleConnectedResponse(connected=True, google_email=google_email)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_google_connection(
    current_user: Annotated[str, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Remove the stored Google OAuth token for the requesting user.

    This does NOT revoke the token at Google's end — the user should also
    visit myaccount.google.com/permissions to fully revoke.
    After calling this, the user must go through the OAuth flow again.
    """
    import uuid

    from sqlalchemy import delete

    from src.data.models.google_token import GoogleToken

    uid = uuid.UUID(str(current_user))
    await session.execute(delete(GoogleToken).where(GoogleToken.user_id == uid))
    await session.commit()
    logger.info("Google token removed for user=%s", current_user)
