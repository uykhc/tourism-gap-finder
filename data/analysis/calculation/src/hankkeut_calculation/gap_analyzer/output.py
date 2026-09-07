"""분석 결과 파일 출력."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import PortfolioReport


def write_json(report: PortfolioReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path

def write_csv(report: PortfolioReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "region_name",
        "area_code",
        "sigungu_code",
        "area_square_km",
        "total_resource_count",
        "total_count_per_square_km",
        "content_type_id",
        "content_type_name",
        "count",
        "percentage",
        "count_per_square_km",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for metric in report.metrics:
            writer.writerow(
                {
                    "region_name": report.region_name,
                    "area_code": report.area_code,
                    "sigungu_code": report.sigungu_code,
                    "area_square_km": report.area_square_km,
                    "total_resource_count": report.total_resource_count,
                    "total_count_per_square_km": (
                        report.total_count_per_square_km
                    ),
                    "content_type_id": metric.content_type_id,
                    "content_type_name": metric.content_type_name,
                    "count": metric.count,
                    "percentage": metric.percentage,
                    "count_per_square_km": metric.count_per_square_km,
                }
            )
    return path
