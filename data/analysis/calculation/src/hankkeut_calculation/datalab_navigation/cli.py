"""Command line entry point for monthly Data Lab navigation-demand imports."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .navigation_demand import (
    DEFAULT_TAXONOMY_PATH,
    build_supply_pressure_report,
    import_navigation_demand_csv,
    load_navigation_demand_taxonomy,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a Data Lab navigation CSV and calculate single-region supply pressure.")
    parser.add_argument(
        "--input", required=True, type=Path,
        help="Data Lab period-total export or legacy monthly CSV.",
    )
    parser.add_argument("--region-name", required=True)
    parser.add_argument("--period-start-ym", help="Period-total CSV start month in YYYYMM.")
    parser.add_argument("--period-end-ym", help="Period-total CSV end month in YYYYMM.")
    parser.add_argument("--content-database-url", help="Postgres URL. Defaults to CONTENT_DATABASE_URL.")
    parser.add_argument("--region-id", required=True, help="Nationwide region identifier (for example 41:115).")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY_PATH)
    parser.add_argument("--months", type=int, default=12, help="Use this many latest available months (default: 12).")
    parser.add_argument("--import-output", type=Path, default=Path("data/analysis/datalab_navigation/navigation_demand_import.json"))
    parser.add_argument("--output", type=Path, default=Path("data/analysis/datalab_navigation/supply_pressure_report.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        taxonomy = load_navigation_demand_taxonomy(args.taxonomy)
        demand_import = import_navigation_demand_csv(
            args.input,
            region_name=args.region_name,
            taxonomy=taxonomy,
            period_start_ym=args.period_start_ym,
            period_end_ym=args.period_end_ym,
        )
        report = build_supply_pressure_report(
            demand_import,
            taxonomy=taxonomy,
            content_database_url=args.content_database_url or os.getenv("CONTENT_DATABASE_URL") or os.getenv("AUTH_DATABASE_URL") or "",
            region_id=args.region_id,
            month_count=args.months,
        )
    except ValueError as exc:
        parser_error = str(exc)
        print(f"Error: {parser_error}")
        return 2
    _write_json(demand_import.to_dict(), args.import_output)
    _write_json(report, args.output)
    print(f"saved import: {args.import_output}")
    print(f"saved report: {args.output}")
    return 0


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
