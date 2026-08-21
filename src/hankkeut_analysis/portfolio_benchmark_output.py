"""포트폴리오 밀도 벤치마크 출력."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .portfolio_benchmark import PortfolioBenchmarkRunReport


def write_portfolio_benchmark_json(
    report: PortfolioBenchmarkRunReport,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _write_dict_rows(path: Path, rows: list[dict], fieldnames: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_portfolio_region_csv(
    report: PortfolioBenchmarkRunReport,
    path: Path,
) -> Path:
    rows = []
    for result in report.region_results:
        definition = result.definition
        for metric in result.report.metrics:
            rows.append(
                {
                    **definition.to_dict(),
                    "total_resource_count": result.report.total_resource_count,
                    "total_count_per_square_km": result.report.total_count_per_square_km,
                    **metric.to_dict(),
                }
            )
    return _write_dict_rows(path, rows, list(rows[0]) if rows else ["region_name"])


def write_portfolio_distribution_csv(
    report: PortfolioBenchmarkRunReport,
    path: Path,
) -> Path:
    rows = [item.to_dict() for item in report.distributions]
    return _write_dict_rows(path, rows, list(rows[0]) if rows else ["group_name"])


def write_portfolio_failure_csv(
    report: PortfolioBenchmarkRunReport,
    path: Path,
) -> Path:
    return _write_dict_rows(
        path,
        [{"region_name": name, "error": error} for name, error in report.failures],
        ["region_name", "error"],
    )
