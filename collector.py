from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from api import fetch_stationboard
from cleaning import clean_stationboard
from database import init_db, insert_observations


def collect_once() -> int:
    snapshot_time = datetime.now(timezone.utc)
    payload = fetch_stationboard()
    observations = clean_stationboard(payload, snapshot_time=snapshot_time)
    return insert_observations(observations)


def collect_loop(poll_seconds: int, days: int) -> None:
    init_db()
    stop_at = datetime.now(timezone.utc) + timedelta(days=days)
    while datetime.now(timezone.utc) < stop_at:
        inserted = collect_once()
        print(f"{datetime.now(timezone.utc).isoformat()} inserted={inserted}", flush=True)
        time.sleep(poll_seconds)
