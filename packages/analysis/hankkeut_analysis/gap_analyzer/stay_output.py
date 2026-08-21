"""체류 전환 빈칸 분석 결과 출력."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .stay_models import StayTransitionReport


ANCHOR_COUNT_KEYS = (
    "food",
    "accommodation",
    "culture",
    "event",
    "shopping",
)


def write_stay_json(report: StayTransitionReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_stay_anchor_csv(report: StayTransitionReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "region_name",
        "hub_base_year_month",
        "rank",
        "tourist_spot_code",
        "name",
        "category_large",
        "category_middle",
        "category_small",
        "longitude",
        "latitude",
        "radius_km",
        *(f"{key}_count" for key in ANCHOR_COUNT_KEYS),
        "total_complement_count",
        "covered_type_count",
        "complement_coverage_score",
        "missing_type_names",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for anchor in report.anchors:
            for radius in anchor.radii:
                counts = {count.key: count.count for count in radius.counts}
                writer.writerow(
                    {
                        "region_name": report.region_name,
                        "hub_base_year_month": report.hub_base_year_month,
                        "rank": anchor.rank,
                        "tourist_spot_code": anchor.tourist_spot_code,
                        "name": anchor.name,
                        "category_large": anchor.category_large,
                        "category_middle": anchor.category_middle,
                        "category_small": anchor.category_small,
                        "longitude": anchor.longitude,
                        "latitude": anchor.latitude,
                        "radius_km": radius.radius_km,
                        **{
                            f"{key}_count": counts.get(key, 0)
                            for key in ANCHOR_COUNT_KEYS
                        },
                        "total_complement_count": (
                            radius.total_complement_count
                        ),
                        "covered_type_count": radius.covered_type_count,
                        "complement_coverage_score": (
                            radius.complement_coverage_score
                        ),
                        "missing_type_names": "|".join(
                            radius.missing_type_names
                        ),
                    }
                )
    return path


def write_stay_summary_csv(report: StayTransitionReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "region_name",
        "hub_base_year_month",
        "radius_km",
        "anchor_count",
        *(f"average_{key}_count" for key in ANCHOR_COUNT_KEYS),
        "average_total_complement_count",
        "average_complement_coverage_score",
        "unique_complement_resource_count",
        "anchor_resource_occurrence_count",
        "overlap_occurrence_count",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for summary in report.regional_summaries:
            averages = dict(summary.average_counts)
            writer.writerow(
                {
                    "region_name": report.region_name,
                    "hub_base_year_month": report.hub_base_year_month,
                    "radius_km": summary.radius_km,
                    "anchor_count": summary.anchor_count,
                    **{
                        f"average_{key}_count": averages.get(key, 0.0)
                        for key in ANCHOR_COUNT_KEYS
                    },
                    "average_total_complement_count": (
                        summary.average_total_complement_count
                    ),
                    "average_complement_coverage_score": (
                        summary.average_complement_coverage_score
                    ),
                    "unique_complement_resource_count": (
                        summary.unique_complement_resource_count
                    ),
                    "anchor_resource_occurrence_count": (
                        summary.anchor_resource_occurrence_count
                    ),
                    "overlap_occurrence_count": (
                        summary.overlap_occurrence_count
                    ),
                }
            )
    return path
