from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


API_URL = "https://search.ch/timetable/api/stationboard.json"
STOP_ID = "8503610"
STOP_NAME = "Zürich, Triemli"
TRAM_LINE = "14"
DEFAULT_POLL_SECONDS = 5 * 60
DEFAULT_COLLECTION_DAYS = 7


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


@dataclass(frozen=True)
class DelayReport:
    observed_departures: int
    delayed_departures: int
    delayed_percentage: float
    range_start: datetime | None
    range_end: datetime | None


def fetch_stationboard() -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "stop": STOP_ID,
            "mode": "depart",
            "limit": 0,
            "show_delays": 1,
            "transportation_types": "tram",
        }
    )
    request = urllib.request.Request(f"{API_URL}?{params}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


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


def get_database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://triemli:triemli@localhost:5432/triemli_delays",
    )


def connect():
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: install psycopg with '.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt'."
        ) from exc
    return psycopg.connect(get_database_url())


def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS tram_departure_observations (
        id BIGSERIAL PRIMARY KEY,
        snapshot_time TIMESTAMPTZ NOT NULL,
        stop_id TEXT NOT NULL,
        stop_name TEXT NOT NULL,
        line TEXT NOT NULL,
        scheduled_departure TIMESTAMP NOT NULL,
        run_id TEXT NOT NULL,
        delay_minutes INTEGER NOT NULL CHECK (delay_minutes >= 0),
        delayed BOOLEAN NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uniq_departure_snapshot UNIQUE (
            snapshot_time,
            scheduled_departure,
            line,
            run_id
        )
    );

    CREATE INDEX IF NOT EXISTS idx_departure_observations_snapshot
        ON tram_departure_observations (snapshot_time);
    CREATE INDEX IF NOT EXISTS idx_departure_observations_line
        ON tram_departure_observations (line);

    ALTER TABLE tram_departure_observations
        DROP COLUMN IF EXISTS terminal_id,
        DROP COLUMN IF EXISTS terminal_name,
        DROP COLUMN IF EXISTS raw;
    """
    with connect() as conn:
        conn.execute(ddl)


def insert_observations(observations: list[DepartureObservation]) -> int:
    if not observations:
        return 0

    sql = """
        INSERT INTO tram_departure_observations (
            snapshot_time,
            stop_id,
            stop_name,
            line,
            scheduled_departure,
            run_id,
            delay_minutes,
            delayed
        )
        VALUES (
            %(snapshot_time)s,
            %(stop_id)s,
            %(stop_name)s,
            %(line)s,
            %(scheduled_departure)s,
            %(run_id)s,
            %(delay_minutes)s,
            %(delayed)s
        )
        ON CONFLICT ON CONSTRAINT uniq_departure_snapshot DO NOTHING
        RETURNING id
    """
    rows = [
        {
            "snapshot_time": item.snapshot_time,
            "stop_id": item.stop_id,
            "stop_name": item.stop_name,
            "line": item.line,
            "scheduled_departure": item.scheduled_departure,
            "run_id": item.run_id,
            "delay_minutes": item.delay_minutes,
            "delayed": item.delayed,
        }
        for item in observations
    ]

    with connect() as conn:
        with conn.cursor() as cursor:
            inserted = 0
            for row in rows:
                cursor.execute(sql, row)
                if cursor.fetchone() is not None:
                    inserted += 1
            return inserted


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


def calculate_report(rows: list[tuple[int, bool]]) -> DelayReport:
    observed = len(rows)
    delayed = sum(1 for _, is_delayed in rows if is_delayed)
    percentage = (delayed / observed * 100) if observed else 0.0
    return DelayReport(
        observed_departures=observed,
        delayed_departures=delayed,
        delayed_percentage=percentage,
        range_start=None,
        range_end=None,
    )


def read_report(days: int) -> DelayReport:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sql = """
        SELECT
            COUNT(*)::int AS observed_departures,
            COUNT(*) FILTER (WHERE delayed)::int AS delayed_departures,
            MIN(snapshot_time) AS range_start,
            MAX(snapshot_time) AS range_end
        FROM tram_departure_observations
        WHERE stop_id = %s
          AND line = %s
          AND snapshot_time >= %s
    """
    with connect() as conn:
        row = conn.execute(sql, (STOP_ID, TRAM_LINE, since)).fetchone()

    observed = row[0] or 0
    delayed = row[1] or 0
    percentage = (delayed / observed * 100) if observed else 0.0
    return DelayReport(
        observed_departures=observed,
        delayed_departures=delayed,
        delayed_percentage=percentage,
        range_start=row[2],
        range_end=row[3],
    )


def print_report(report: DelayReport) -> None:
    print(f"Observed departures: {report.observed_departures}")
    print(f"Delayed departures: {report.delayed_departures}")
    print(f"Delayed percentage: {report.delayed_percentage:.2f}%")
    print(f"Range start: {report.range_start.isoformat() if report.range_start else 'n/a'}")
    print(f"Range end: {report.range_end.isoformat() if report.range_end else 'n/a'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and report Triemli tram 14 delays.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create PostgreSQL tables.")
    subparsers.add_parser("collect-once", help="Collect and store one stationboard snapshot.")

    loop_parser = subparsers.add_parser("collect-loop", help="Collect snapshots repeatedly.")
    loop_parser.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    loop_parser.add_argument("--days", type=int, default=DEFAULT_COLLECTION_DAYS)

    report_parser = subparsers.add_parser("report", help="Calculate delay frequency.")
    report_parser.add_argument("--days", type=int, default=DEFAULT_COLLECTION_DAYS)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "init-db":
        init_db()
        print("Database initialized.")
    elif args.command == "collect-once":
        init_db()
        inserted = collect_once()
        print(f"Inserted observations: {inserted}")
    elif args.command == "collect-loop":
        collect_loop(poll_seconds=args.poll_seconds, days=args.days)
    elif args.command == "report":
        print_report(read_report(days=args.days))


if __name__ == "__main__":
    main()
