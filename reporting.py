from __future__ import annotations

from datetime import datetime, timedelta, timezone

from config import STOP_ID, TRAM_LINE
from database import connect
from models.delay_report import DelayReport


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
