"""시군구 구조 특성으로 유사 지역 그룹과 근접 레퍼런스를 만든다.

관광 콘텐츠 공급량은 빈칸 진단 지표이므로 기본 유사도 계산에서 제외한다.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DOMAIN_WEIGHTS = {
    "urban_scale": 0.25,
    "geography": 0.25,
    "accessibility": 0.20,
    "tourism_product": 0.15,
    "facility_structure": 0.10,
    "climate": 0.05,
}
NUMERIC_DOMAINS = {
    "urban_scale": ("population", "population_density"),
    "geography": ("area_square_km", "forest_ratio", "water_ratio", "mean_elevation_m"),
    "accessibility": ("gateway_access_minutes", "rail_access_score", "expressway_access_score"),
    "facility_structure": ("commercial_facility_ratio", "industrial_facility_ratio", "residential_facility_ratio"),
    "climate": ("annual_mean_temperature_c", "annual_precipitation_mm", "temperature_range_c"),
}


@dataclass(frozen=True, slots=True)
class SimilarityRegion:
    region_code: str
    region_name: str
    province_name: str
    administrative_type: str
    values: dict[str, float]
    core_products: frozenset[str]


@dataclass(frozen=True, slots=True)
class SimilarityConfig:
    input_csv: Path
    groups_output_csv: Path
    neighbors_output_csv: Path
    report_output_json: Path
    groups_per_partition: int
    partition_by_administrative_type: bool
    neighbor_count: int
    weights: dict[str, float]


def load_similarity_config(path: Path) -> SimilarityConfig:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"유사 지역 설정 파일이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"유사 지역 설정 JSON 형식이 올바르지 않습니다: {exc}") from exc
    required = ("input_csv", "groups_output_csv", "neighbors_output_csv", "report_output_json")
    missing = [key for key in required if not str(value.get(key, "")).strip()]
    if missing:
        raise ValueError("유사 지역 설정 필수 항목 누락: " + ", ".join(missing))
    weights = {**DOMAIN_WEIGHTS, **value.get("weights", {})}
    unknown = set(weights) - set(DOMAIN_WEIGHTS)
    if unknown:
        raise ValueError("알 수 없는 유사도 가중치: " + ", ".join(sorted(unknown)))
    if any(not isinstance(weight, (int, float)) or weight < 0 for weight in weights.values()):
        raise ValueError("유사도 가중치는 0 이상의 숫자여야 합니다.")
    if not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        raise ValueError("유사도 가중치의 합은 1이어야 합니다.")
    groups_per_partition = int(value.get("groups_per_partition", 0))
    if groups_per_partition < 0:
        raise ValueError("groups_per_partition는 0 이상이어야 합니다.")
    neighbor_count = int(value.get("neighbor_count", 3))
    if neighbor_count < 1:
        raise ValueError("neighbor_count는 1 이상이어야 합니다.")
    return SimilarityConfig(
        input_csv=Path(value["input_csv"]),
        groups_output_csv=Path(value["groups_output_csv"]),
        neighbors_output_csv=Path(value["neighbors_output_csv"]),
        report_output_json=Path(value["report_output_json"]),
        groups_per_partition=groups_per_partition,
        partition_by_administrative_type=bool(value.get("partition_by_administrative_type", True)),
        neighbor_count=neighbor_count,
        weights=weights,
    )


def load_similarity_regions(path: Path) -> tuple[SimilarityRegion, ...]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except FileNotFoundError as exc:
        raise ValueError(f"유사도 입력 CSV가 없습니다: {path}") from exc
    required = {"region_code", "region_name", "province_name", "administrative_type", "core_products"}
    if not rows:
        raise ValueError("유사도 입력 CSV에 지역 행이 없습니다.")
    missing = required - set(rows[0])
    if missing:
        raise ValueError("유사도 입력 CSV 필수 열 누락: " + ", ".join(sorted(missing)))
    regions = []
    numeric_fields = tuple(field for fields in NUMERIC_DOMAINS.values() for field in fields)
    for row in rows:
        values = {
            field: _optional_float(row.get(field, ""), field=field, region_name=row["region_name"])
            for field in numeric_fields
        }
        regions.append(
            SimilarityRegion(
                region_code=row["region_code"].strip(),
                region_name=row["region_name"].strip(),
                province_name=row["province_name"].strip(),
                administrative_type=row["administrative_type"].strip(),
                values={key: value for key, value in values.items() if value is not None},
                core_products=frozenset(item.strip() for item in row["core_products"].split("|") if item.strip()),
            )
        )
    if any(not region.region_code or not region.region_name for region in regions):
        raise ValueError("region_code와 region_name은 비어 있을 수 없습니다.")
    if len({region.region_code for region in regions}) != len(regions):
        raise ValueError("region_code가 중복되었습니다.")
    return tuple(regions)


def build_similarity_result(
    regions: tuple[SimilarityRegion, ...],
    *,
    weights: dict[str, float],
    groups_per_partition: int = 0,
    partition_by_administrative_type: bool = True,
    neighbor_count: int = 3,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if len(regions) < 2:
        raise ValueError("유사 지역 분석에는 2개 이상의 지역이 필요합니다.")
    partitions: dict[str, list[SimilarityRegion]] = defaultdict(list)
    for region in regions:
        partitions[region.administrative_type if partition_by_administrative_type else "all"].append(region)

    group_rows: list[dict[str, Any]] = []
    neighbor_rows: list[dict[str, Any]] = []
    report_partitions: dict[str, Any] = {}
    for partition_name, members in sorted(partitions.items()):
        if len(members) < 2:
            continue
        distances = _distance_matrix(members, weights)
        group_count = groups_per_partition or _recommended_group_count(len(members))
        group_count = min(group_count, len(members))
        assignments, medoids = _k_medoids(members, distances, group_count)
        report_partitions[partition_name] = {
            "region_count": len(members), "group_count": group_count,
            "medoids": [members[index].region_code for index in medoids],
        }
        for index, region in enumerate(members):
            group_rows.append({
                "region_code": region.region_code, "region_name": region.region_name,
                "province_name": region.province_name, "administrative_type": region.administrative_type,
                "similarity_partition": partition_name,
                "similarity_group": f"{partition_name}-{assignments[index] + 1}",
                "group_medoid_region_code": members[medoids[assignments[index]]].region_code,
                "group_medoid_region_name": members[medoids[assignments[index]]].region_name,
                "available_domains": "|".join(_available_domains(region)),
            })
            nearest = sorted(
                (distance, other_index)
                for other_index, distance in enumerate(distances[index])
                if other_index != index
            )[:neighbor_count]
            for rank, (distance, other_index) in enumerate(nearest, start=1):
                other = members[other_index]
                neighbor_rows.append({
                    "region_code": region.region_code, "region_name": region.region_name,
                    "similarity_partition": partition_name, "neighbor_rank": rank,
                    "neighbor_region_code": other.region_code, "neighbor_region_name": other.region_name,
                    "distance": round(distance, 6), "similarity_score": round((1 - distance) * 100, 4),
                })
    report = {
        "region_count": len(regions), "partition_by_administrative_type": partition_by_administrative_type,
        "weights": weights, "partitions": report_partitions,
        "note": "관광 콘텐츠 개수·밀도·유형 비율은 빈칸 진단용으로, 이 유사도 계산에는 넣지 않았습니다.",
    }
    return group_rows, neighbor_rows, report


def write_similarity_result(
    group_rows: list[dict[str, Any]], neighbor_rows: list[dict[str, Any]], report: dict[str, Any], *, config: SimilarityConfig,
) -> None:
    _write_csv(config.groups_output_csv, group_rows, ["region_code"])
    _write_csv(config.neighbors_output_csv, neighbor_rows, ["region_code"])
    config.report_output_json.parent.mkdir(parents=True, exist_ok=True)
    config.report_output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _distance_matrix(regions: list[SimilarityRegion], weights: dict[str, float]) -> list[list[float]]:
    ranges = {
        field: max(values) - min(values)
        for fields in NUMERIC_DOMAINS.values()
        for field in fields
        if (values := [region.values[field] for region in regions if field in region.values])
    }
    matrix = [[0.0] * len(regions) for _ in regions]
    for left_index, left in enumerate(regions):
        for right_index in range(left_index + 1, len(regions)):
            right = regions[right_index]
            domains = _domain_distances(left, right, ranges)
            active_weight = sum(weights[name] for name in domains)
            if active_weight == 0:
                raise ValueError(f"{left.region_name}와 {right.region_name} 사이에 비교 가능한 특성이 없습니다.")
            distance = sum(weights[name] * value for name, value in domains.items()) / active_weight
            matrix[left_index][right_index] = matrix[right_index][left_index] = distance
    return matrix


def _domain_distances(left: SimilarityRegion, right: SimilarityRegion, ranges: dict[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for domain, fields in NUMERIC_DOMAINS.items():
        values = []
        for field in fields:
            if field not in left.values or field not in right.values:
                continue
            value_range = ranges.get(field, 0)
            values.append(0.0 if value_range == 0 else abs(left.values[field] - right.values[field]) / value_range)
        if values:
            result[domain] = sum(values) / len(values)
    if left.core_products and right.core_products:
        result["tourism_product"] = 1 - len(left.core_products & right.core_products) / len(left.core_products | right.core_products)
    return result


def _k_medoids(regions: list[SimilarityRegion], distances: list[list[float]], group_count: int) -> tuple[list[int], list[int]]:
    medoids = [min(range(len(regions)), key=lambda index: sum(distances[index]))]
    while len(medoids) < group_count:
        medoids.append(max((index for index in range(len(regions)) if index not in medoids), key=lambda index: min(distances[index][medoid] for medoid in medoids)))
    for _ in range(30):
        assignments = [min(range(len(medoids)), key=lambda group: distances[index][medoids[group]]) for index in range(len(regions))]
        updated = []
        for group, medoid in enumerate(medoids):
            members = [index for index, assignment in enumerate(assignments) if assignment == group]
            updated.append(min(members, key=lambda candidate: sum(distances[candidate][other] for other in members)) if members else medoid)
        if updated == medoids:
            return assignments, medoids
        medoids = updated
    return assignments, medoids


def _recommended_group_count(region_count: int) -> int:
    return max(2, round(math.sqrt(region_count / 2)))


def _available_domains(region: SimilarityRegion) -> list[str]:
    available = [domain for domain, fields in NUMERIC_DOMAINS.items() if any(field in region.values for field in fields)]
    return available + (["tourism_product"] if region.core_products else [])


def _optional_float(value: str | None, *, field: str, region_name: str) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value.replace(",", ""))
    except ValueError as exc:
        raise ValueError(f"{region_name}의 {field} 값이 숫자가 아닙니다.") from exc


def _write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else fallback_fields
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
