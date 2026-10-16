from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.api.v1.routes.workout import _serialize_session
from src.core.models.workout_schemas import WorkoutLogRequest
from src.data.models.fitness import WorkoutLog, WorkoutSession, WorkoutSet


def test_workout_request_tracks_weight_per_set():
    payload = WorkoutLogRequest.model_validate(
        {
            "entries": [
                {
                    "exercise": "Bench Press",
                    "sets": [
                        {"reps": 8, "weight_kg": 60.0},
                        {"reps": 6, "weight_kg": 65.5},
                    ],
                }
            ]
        }
    )

    entry = payload.entries[0]
    assert len(entry.sets) == 2
    assert sum(item.reps for item in entry.sets) == 14
    assert entry.sets[1].weight_kg == 65.5


def test_workout_request_rejects_client_supplied_user_id():
    with pytest.raises(ValidationError):
        WorkoutLogRequest.model_validate(
            {
                "user_id": str(uuid4()),
                "entries": [
                    {
                        "exercise": "Bench Press",
                        "sets": [{"reps": 8, "weight_kg": 60.0}],
                    }
                ],
            }
        )


def test_workout_entry_rejects_parent_level_weight():
    with pytest.raises(ValidationError):
        WorkoutLogRequest.model_validate(
            {
                "entries": [
                    {
                        "exercise": "Bench Press",
                        "weight_kg": 60.0,
                        "sets": [{"reps": 8, "weight_kg": 60.0}],
                    }
                ]
            }
        )


def test_history_serializes_sets_under_weightless_entry_parent():
    entry = WorkoutLog(
        id=1,
        session_id=uuid4(),
        user_id=uuid4(),
        exercise="Bench Press",
        exercise_type="strength",
        muscle_group="chest",
        sets_count=2,
        total_reps=14,
        rpe=Decimal("7.0"),
        notes="",
        form_score=None,
        range_of_motion=None,
        device_data={},
        sets=[
            WorkoutSet(
                id=uuid4(), log_id=1, user_id=uuid4(), set_number=1,
                reps=8, weight_kg=Decimal("60.0"), rpe=None,
            ),
            WorkoutSet(
                id=uuid4(), log_id=1, user_id=uuid4(), set_number=2,
                reps=6, weight_kg=Decimal("65.5"), rpe=None,
            ),
        ],
    )
    workout = WorkoutSession(
        id=uuid4(),
        user_id=uuid4(),
        started_at=datetime(2026, 10, 9, tzinfo=timezone.utc),
        mood=8,
        energy=7,
        sleep_quality=9,
        notes="",
        entries=[entry],
    )

    record = _serialize_session(workout)
    serialized_entry = record["entries"][0]
    assert serialized_entry["sets_count"] == 2
    assert serialized_entry["total_reps"] == 14
    assert "weight_kg" not in serialized_entry
    assert [item["weight_kg"] for item in serialized_entry["sets"]] == [60.0, 65.5]
