from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DelayReport:
    observed_departures: int
    delayed_departures: int
    delayed_percentage: float
    range_start: datetime | None
    range_end: datetime | None
