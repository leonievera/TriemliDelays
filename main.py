from __future__ import annotations

import argparse

from collector import collect_loop, collect_once
from config import DEFAULT_COLLECTION_DAYS, DEFAULT_POLL_SECONDS
from database import init_db
from reporting import print_report, read_report


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
