"""관광지 벤치마크 배치 분석 출력."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .benchmark import BenchmarkRunReport

COUNT_KEYS = ("food", "accommodation", "culture", "event", "shopping")


def write_benchmark_json(report: BenchmarkRunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def write_benchmark_anchor_csv(report: BenchmarkRunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "benchmark_name",
        "base_year_month",
        "province_name",
        "region_name",
        "sample_group",
        "rank",
        "tourist_spot_code",
        "name",
        "category_large",
        "category_middle",
        "category_small",
        "longitude",
        "latitude",
        "radius_km",
        *(f"{key}_count" for key in COUNT_KEYS),
        "total_complement_count",
        "covered_type_count",
        "complement_coverage_score",
        "missing_type_names",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for region_result in report.region_results:
            definition = region_result.definition
            for anchor in region_result.report.anchors:
                for radius in anchor.radii:
                    counts = {count.key: count.count for count in radius.counts}
                    writer.writerow(
                        {
                            "benchmark_name": report.benchmark_name,
                            "base_year_month": report.base_year_month,
                            "province_name": definition.province_name,
                            "region_name": definition.region_name,
                            "sample_group": definition.sample_group,
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
                                f"{key}_count": counts[key]
                                for key in COUNT_KEYS
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


def write_benchmark_distribution_csv(
    report: BenchmarkRunReport,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "benchmark_name",
        "base_year_month",
        "grouping_dimension",
        "group_name",
        "radius_km",
        "metric_key",
        "sample_count",
        "zero_count",
        "zero_rate_percentage",
        "minimum",
        "median",
        "p75",
        "maximum",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for distribution in report.distributions:
            writer.writerow(
                {
                    "benchmark_name": report.benchmark_name,
                    "base_year_month": report.base_year_month,
                    **distribution.to_dict(),
                }
            )
    return path


def write_benchmark_failure_csv(report: BenchmarkRunReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("region_name", "error"),
        )
        writer.writeheader()
        for region_name, error in report.failures:
            writer.writerow({"region_name": region_name, "error": error})
    return path
