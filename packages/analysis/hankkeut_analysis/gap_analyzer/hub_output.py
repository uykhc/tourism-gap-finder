"""중심 관광지 상위 목록 출력."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import HubTouristSpotReport


def write_hub_json(report: HubTouristSpotReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_hub_csv(report: HubTouristSpotReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "region_name",
        "base_year_month",
        "area_code",
        "sigungu_code",
        "rank",
        "tourist_spot_code",
        "name",
        "category_large",
        "category_middle",
        "category_small",
        "longitude",
        "latitude",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for spot in report.spots:
            writer.writerow(
                {
                    "region_name": report.region_name,
                    "base_year_month": report.base_year_month,
                    "area_code": report.area_code,
                    "sigungu_code": report.sigungu_code,
                    "rank": spot.rank,
                    "tourist_spot_code": spot.tourist_spot_code,
                    "name": spot.name,
                    "category_large": spot.category_large,
                    "category_middle": spot.category_middle,
                    "category_small": spot.category_small,
                    "longitude": spot.longitude,
                    "latitude": spot.latitude,
                }
            )
    return path
