from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DepartureObservation:
    snapshot_time: datetime
    stop_id: str
    stop_name: str
    line: str
    scheduled_departure: datetime
    run_id: str
    delay_minutes: int
    delayed: bool
