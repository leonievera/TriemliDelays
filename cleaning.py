from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config import STOP_ID, STOP_NAME, TRAM_LINE
from models.departure_observation import DepartureObservation


def clean_stationboard(
    payload: dict[str, Any],
    snapshot_time: datetime | None = None,
) -> list[DepartureObservation]:
    snapshot = snapshot_time or datetime.now(timezone.utc)
    observations: list[DepartureObservation] = []

    for row in payload.get("connections") or []:
        if not isinstance(row, dict):
            continue
        if row.get("type") != "tram" or str(row.get("line")) != TRAM_LINE:
            continue

        run_id = row.get("*Z") or row.get("number") or row.get("tripid")
        scheduled_departure = parse_datetime(row.get("time"))
        if not run_id or scheduled_departure is None:
            continue

        delay_minutes = parse_int_minutes(row.get("dep_delay"))
        observations.append(
            DepartureObservation(
                snapshot_time=snapshot,
                stop_id=STOP_ID,
                stop_name=STOP_NAME,
                line=TRAM_LINE,
                scheduled_departure=scheduled_departure,
                run_id=str(run_id),
                delay_minutes=delay_minutes,
                delayed=delay_minutes > 0,
            )
        )

    return observations


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_int_minutes(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str):
        cleaned = value.strip().lower().replace("min", "").replace("+", "")
        try:
            return max(0, int(float(cleaned)))
        except ValueError:
            return 0
    return 0
