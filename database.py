from __future__ import annotations

import os

from models.departure_observation import DepartureObservation


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
