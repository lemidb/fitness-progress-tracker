"""
Google Sheets service.

Uses gspread (service account or OAuth).
The sheet acts as a lightweight data warehouse for workout logs.
All heavy analytics queries run on the in-memory DataFrame; we
never issue per-cell reads in hot paths.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gspread
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import get_settings
from src.core.models.domain import (
    PersonalRecord,
    SessionMetadata,
    WorkoutEntry,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SHEET_HEADERS = [
    "date", "user_id", "exercise", "exercise_type", "muscle_group",
    "sets", "reps", "weight_kg", "rpe", "volume", "one_rm",
    "mood", "energy", "sleep_quality", "notes",
    "form_score", "range_of_motion", "device_data", "timestamp",
]


class GoogleSheetsService:

    def __init__(self) -> None:
        self.settings = get_settings()
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._client: gspread.Client | None = None
        self._worksheet: gspread.Worksheet | None = None

    # ── Auth / Setup ─────────────────────────────────────────────────────────

    def _authorize(self) -> gspread.Client:
        sa_file = self.settings.google_service_account_file
        if sa_file and Path(sa_file).exists():
            creds = service_account.Credentials.from_service_account_file(
                sa_file, scopes=SCOPES
            )
            return gspread.authorize(creds)

        # OAuth flow
        token_path = Path(self.settings.google_token_file)
        oauth_path = Path(self.settings.google_credentials_file)
        creds: Credentials | None = None

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            elif oauth_path.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(oauth_path), SCOPES)
                creds = flow.run_local_server(port=0)
                token_path.write_text(creds.to_json())
            else:
                raise FileNotFoundError(
                    "No Google credentials found for Sheets. "
                    "See README for setup instructions."
                )
        return gspread.authorize(creds)

    @property
    def client(self) -> gspread.Client:
        if self._client is None:
            self._client = self._authorize()
        return self._client

    @property
    def worksheet(self) -> gspread.Worksheet:
        if self._worksheet is None:
            spreadsheet = self.client.open_by_key(self.settings.google_spreadsheet_key)
            try:
                self._worksheet = spreadsheet.worksheet(self.settings.google_worksheet_name)
            except gspread.WorksheetNotFound:
                self._worksheet = spreadsheet.add_worksheet(
                    self.settings.google_worksheet_name, rows=5000, cols=len(SHEET_HEADERS)
                )
                self._worksheet.append_row(SHEET_HEADERS)
                logger.info("Created new worksheet: %s", self.settings.google_worksheet_name)
        return self._worksheet

    def _ensure_headers(self) -> None:
        """Write headers if the sheet is empty."""
        existing = self.worksheet.row_values(1)
        if not existing:
            self.worksheet.append_row(SHEET_HEADERS)
            logger.info("Sheet initialised with headers")

    # ── Write ────────────────────────────────────────────────────────────────

    async def log_workout(
        self,
        user_id: str,
        entries: list[WorkoutEntry],
        metadata: SessionMetadata,
    ) -> dict[str, Any]:
        """
        Append all workout entries in a single batch write.
        Returns logged count + per-entry insights.
        """
        rows: list[list] = []
        insights: list[dict] = []
        today = datetime.utcnow().strftime("%Y-%m-%d")
        now_iso = datetime.utcnow().isoformat()

        # Fetch current max weights to detect PRs (single sheet read)
        history_df = await self._load_user_history(user_id)

        for entry in entries:
            row = [
                today,
                user_id,
                entry.exercise,
                entry.exercise_type.value,
                entry.muscle_group.value,
                entry.sets,
                entry.reps,
                entry.weight_kg,
                entry.rpe,
                entry.volume,
                round(entry.estimated_1rm, 2),
                metadata.mood,
                metadata.energy,
                metadata.sleep_quality,
                entry.notes,
                entry.form_score if entry.form_score is not None else "",
                entry.range_of_motion if entry.range_of_motion is not None else "",
                entry.device_data,
                now_iso,
            ]
            rows.append(row)
            insights.append(self._build_insight(entry, history_df))

        # Batch write in executor (gspread is sync)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor,
            lambda: self.worksheet.append_rows(rows, value_input_option="USER_ENTERED"),
        )

        total_volume = sum(e.volume for e in entries)
        logger.info("Logged %d entries for user=%s (volume=%.1f)", len(rows), user_id, total_volume)

        return {
            "logged_entries": len(rows),
            "total_volume": total_volume,
            "insights": insights,
            "timestamp": now_iso,
        }

    # ── Read ─────────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _load_user_history(
        self,
        user_id: str,
        exercise: str | None = None,
        days: int = 365,
    ) -> pd.DataFrame:
        """Load all records for a user into a DataFrame (single API call)."""
        loop = asyncio.get_event_loop()
        records = await loop.run_in_executor(
            self._executor, self.worksheet.get_all_records
        )

        df = pd.DataFrame(records)
        if df.empty:
            return df

        df = df[df["user_id"] == user_id].copy()
        if df.empty:
            return df

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        cutoff = datetime.utcnow() - timedelta(days=days)
        df = df[df["date"] >= cutoff]

        # Coerce numeric columns
        for col in ["weight_kg", "reps", "sets", "volume", "one_rm", "rpe"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        if exercise:
            df = df[df["exercise"].str.lower() == exercise.lower()]

        return df.sort_values("date")

    async def get_user_history(
        self,
        user_id: str,
        exercise: str | None = None,
        days: int = 90,
    ) -> pd.DataFrame:
        return await self._load_user_history(user_id, exercise, days)

    async def get_exercise_progress(self, user_id: str, exercise: str) -> dict:
        df = await self._load_user_history(user_id, exercise)

        if df.empty:
            return {"error": "No data found", "exercise": exercise}

        trend = self._calculate_trend(df)
        prs = self._find_prs(df, exercise)

        return {
            "exercise": exercise,
            "date_range": {
                "start": df["date"].min().isoformat(),
                "end": df["date"].max().isoformat(),
            },
            "total_workouts": len(df),
            "max_weight": float(df["weight_kg"].max()),
            "avg_weight": float(df["weight_kg"].mean()),
            "max_volume": float(df["volume"].max()),
            "avg_volume": float(df["volume"].mean()),
            "trend": trend,
            "prs": [pr.__dict__ for pr in prs],
        }

    # ── Analytics helpers ────────────────────────────────────────────────────

    def _calculate_trend(self, df: pd.DataFrame) -> dict:
        if len(df) < 3:
            return {"direction": "insufficient_data", "slope": 0.0, "projected_weight": None}

        x = np.arange(len(df)).reshape(-1, 1)
        y = df["weight_kg"].values

        # Simple least-squares regression (avoid sklearn import until Phase 2)
        x_flat = x.flatten().astype(float)
        slope = float(np.polyfit(x_flat, y, 1)[0])

        projected_idx = len(df) + 7
        projected = float(np.polyval(np.polyfit(x_flat, y, 1), projected_idx))

        direction = (
            "improving" if slope > 0.1
            else "declining" if slope < -0.1
            else "maintaining"
        )

        return {
            "direction": direction,
            "slope": round(slope, 3),
            "projected_weight": round(projected, 1),
        }

    def _find_prs(self, df: pd.DataFrame, exercise: str) -> list[PersonalRecord]:
        prs: list[PersonalRecord] = []

        if df.empty:
            return prs

        # Weight PR
        idx = df["weight_kg"].idxmax()
        row = df.loc[idx]
        prs.append(PersonalRecord(
            exercise=exercise,
            type="weight_pr",
            value=float(row["weight_kg"]),
            date=row["date"].isoformat(),
            reps=int(row.get("reps", 0)),
        ))

        # Volume PR (single session)
        idx_v = df["volume"].idxmax()
        row_v = df.loc[idx_v]
        prs.append(PersonalRecord(
            exercise=exercise,
            type="volume_pr",
            value=float(row_v["volume"]),
            date=row_v["date"].isoformat(),
        ))

        # Estimated 1RM PR
        if "one_rm" in df.columns:
            idx_r = df["one_rm"].idxmax()
            row_r = df.loc[idx_r]
            prs.append(PersonalRecord(
                exercise=exercise,
                type="one_rm_pr",
                value=float(row_r["one_rm"]),
                date=row_r["date"].isoformat(),
                reps=int(row_r.get("reps", 0)),
            ))

        return prs

    def _build_insight(self, entry: WorkoutEntry, history_df: pd.DataFrame) -> dict:
        """Per-entry coaching insight based on history."""
        prev_max = 0.0
        if not history_df.empty and "exercise" in history_df.columns:
            prev = history_df[history_df["exercise"].str.lower() == entry.exercise.lower()]
            if not prev.empty:
                prev_max = float(prev["weight_kg"].max())

        is_pr = entry.weight_kg > prev_max and prev_max > 0
        suggestion = self._weight_suggestion(entry)

        return {
            "exercise": entry.exercise,
            "is_pr": is_pr,
            "prev_max_kg": prev_max,
            "form_quality": (
                "good" if (entry.form_score or 0) >= 7
                else "needs_improvement" if (entry.form_score or 0) > 0
                else "not_recorded"
            ),
            "suggestion": suggestion,
        }

    @staticmethod
    def _weight_suggestion(entry: WorkoutEntry) -> str:
        w, r, rpe = entry.weight_kg, entry.reps, entry.rpe
        if rpe < 6 and r >= 12:
            return f"Consider increasing to {int(w * 1.05)}kg next session"
        if rpe > 8.5 and r < 5:
            return f"Consider reducing to {int(w * 0.9)}kg and focusing on form"
        if rpe <= 7 and 6 <= r <= 12:
            return "Good working weight — maintain and aim for one extra rep"
        return "Solid session. Maintain current progression."
