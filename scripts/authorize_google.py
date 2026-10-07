"""
One-time Google OAuth authorisation script.

Run this ONCE from your terminal (outside the FastAPI server) to generate
credentials/token.json covering all required scopes.

Usage:
    python scripts/authorize_google.py

The browser will open; sign in with the Google account that owns the
spreadsheet/calendar. The resulting token.json is written to the path
configured in .env (default: credentials/token.json).

After this script succeeds, the FastAPI server will use the saved token
automatically and will never open a browser again (it auto-refreshes).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402
from src.core.config import get_settings  # noqa: E402

# All scopes required by the app (Sheets + Drive + Calendar).
# A single token covering all scopes avoids scope-mismatch re-auth loops.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def main() -> None:
    settings = get_settings()

    oauth_path = Path(settings.google_credentials_file)
    token_path = Path(settings.google_token_file)

    if not oauth_path.exists():
        print(f"[ERROR] OAuth credentials file not found: {oauth_path}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials.")
        sys.exit(1)

    print(f"[INFO] Using OAuth credentials: {oauth_path}")
    print(f"[INFO] Token will be saved to:  {token_path}")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(oauth_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")

    print()
    print(f"[OK] token.json written to {token_path}")
    print("[OK] The server will now use this token and refresh it automatically.")


if __name__ == "__main__":
    main()
