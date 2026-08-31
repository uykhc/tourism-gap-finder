"""여러 지역의 중심 관광지 벤치마크 집계."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hankkeut_calculation.gap_analyzer.stay_models import StayTransitionReport

BENCHMARK_METRIC_KEYS = (
    "food",
    "accommodation",
    "culture",
    "event",
    "shopping",
    "total_complement_count",
    "complement_coverage_score",
)


@dataclass(frozen=True, slots=True)
class BenchmarkRegion:
    region_name: str
    province_name: str
    sample_group: str
    hub_area_code: str
    hub_sigungu_code: str
    tour_area_code: str
    tour_sigungu_code: str
    tour_sigungu_name: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BenchmarkRegion":
        required_fields = (
            "region_name",
            "province_name",
            "sample_group",
            "hub_area_code",
            "hub_sigungu_code",
            "tour_area_code",
            "tour_sigungu_code",
            "tour_sigungu_name",
        )
        missing = [field for field in required_fields if not str(value.get(field, "")).strip()]
        if missing:
            raise ValueError(
                "벤치마크 지역 설정에 필수 항목이 없습니다: "
                + ", ".join(missing)
            )
        return cls(**{field: str(value[field]).strip() for field in required_fields})

    def to_dict(self) -> dict[str, str]:
        return {
            "region_name": self.region_name,
            "province_name": self.province_name,
            "sample_group": self.sample_group,
            "hub_area_code": self.hub_area_code,
            "hub_sigungu_code": self.hub_sigungu_code,
            "tour_area_code": self.tour_area_code,
            "tour_sigungu_code": self.tour_sigungu_code,
            "tour_sigungu_name": self.tour_sigungu_name,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    benchmark_name: str
    base_year_month: str
    anchor_count_per_region: int
    hub_category_large: str
    excluded_hub_category_middle: tuple[str, ...]
    radii_km: tuple[float, ...]
    regions: tuple[BenchmarkRegion, ...]
    hub_category_middle: str | None = None
    output_slug: str = "gyeonggi_benchmark"


@dataclass(frozen=True, slots=True)
class BenchmarkRegionResult:
    definition: BenchmarkRegion
    report: StayTransitionReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "report": self.report.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class BenchmarkMetricDistribution:
    grouping_dimension: str
    group_name: str
    radius_km: float
    metric_key: str
    sample_count: int
    zero_count: int
    zero_rate_percentage: float
    minimum: float
    median: float
    p75: float
    maximum: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "grouping_dimension": self.grouping_dimension,
            "group_name": self.group_name,
            "radius_km": self.radius_km,
            "metric_key": self.metric_key,
            "sample_count": self.sample_count,
            "zero_count": self.zero_count,
            "zero_rate_percentage": self.zero_rate_percentage,
            "minimum": self.minimum,
            "median": self.median,
            "p75": self.p75,
            "maximum": self.maximum,
        }


@dataclass(frozen=True, slots=True)
class BenchmarkRunReport:
    benchmark_name: str
    generated_at: str
    base_year_month: str
    anchor_count_per_region: int
    hub_category_large: str
    excluded_hub_category_middle: tuple[str, ...]
    radii_km: tuple[float, ...]
    region_results: tuple[BenchmarkRegionResult, ...]
    distributions: tuple[BenchmarkMetricDistribution, ...]
    failures: tuple[tuple[str, str], ...]
    hub_category_middle: str | None = None
    output_slug: str = "gyeonggi_benchmark"

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "generated_at": self.generated_at,
            "base_year_month": self.base_year_month,
            "anchor_count_per_region": self.anchor_count_per_region,
            "hub_category_large": self.hub_category_large,
            "hub_category_middle": self.hub_category_middle,
            "excluded_hub_category_middle": list(
                self.excluded_hub_category_middle
            ),
            "radii_km": list(self.radii_km),
            "successful_region_count": len(self.region_results),
            "failed_region_count": len(self.failures),
            "region_results": [result.to_dict() for result in self.region_results],
            "distributions": [
                distribution.to_dict() for distribution in self.distributions
            ],
            "failures": [
                {"region_name": region_name, "error": error}
                for region_name, error in self.failures
            ],
        }


def load_benchmark_config(path: Path) -> BenchmarkConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"벤치마크 설정 파일이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"벤치마크 설정 JSON 형식이 올바르지 않습니다: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("벤치마크 설정 JSON 최상위 값은 객체여야 합니다.")

    benchmark_name = str(payload.get("benchmark_name", "")).strip()
    base_year_month = str(payload.get("base_year_month", "")).strip()
    if not benchmark_name:
        raise ValueError("benchmark_name이 비어 있습니다.")
    if not re.fullmatch(r"\d{6}", base_year_month):
        raise ValueError("base_year_month는 YYYYMM 형식이어야 합니다.")
    if not 1 <= int(base_year_month[4:]) <= 12:
        raise ValueError("base_year_month의 월은 01부터 12까지여야 합니다.")

    try:
        anchor_count = int(payload.get("anchor_count_per_region"))
    except (TypeError, ValueError) as exc:
        raise ValueError("anchor_count_per_region은 정수여야 합니다.") from exc
    if not 1 <= anchor_count <= 100:
        raise ValueError("anchor_count_per_region은 1부터 100까지여야 합니다.")

    hub_category_large = str(payload.get("hub_category_large", "")).strip()
    if not hub_category_large:
        raise ValueError("hub_category_large가 비어 있습니다.")
    raw_excluded_middle = payload.get("excluded_hub_category_middle", [])
    if not isinstance(raw_excluded_middle, list) or not all(
        isinstance(category, str) for category in raw_excluded_middle
    ):
        raise ValueError("excluded_hub_category_middle은 문자열 배열이어야 합니다.")
    excluded_middle = tuple(
        dict.fromkeys(
            category.strip()
            for category in raw_excluded_middle
            if category.strip()
        )
    )
    hub_category_middle = (
        str(payload.get("hub_category_middle", "")).strip() or None
    )
    if (
        hub_category_middle is not None
        and hub_category_middle in excluded_middle
    ):
        raise ValueError(
            "hub_category_middle은 excluded_hub_category_middle에 "
            "포함될 수 없습니다."
        )

    output_slug = str(
        payload.get("output_slug", "gyeonggi_benchmark")
    ).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", output_slug):
        raise ValueError(
            "output_slug는 영문자, 숫자, 밑줄, 하이픈만 사용할 수 있습니다."
        )

    raw_radii = payload.get("radii_km")
    if not isinstance(raw_radii, list) or not raw_radii:
        raise ValueError("radii_km는 하나 이상의 숫자 배열이어야 합니다.")
    try:
        radii = tuple(sorted({float(radius) for radius in raw_radii}))
    except (TypeError, ValueError) as exc:
        raise ValueError("radii_km에는 숫자만 입력해야 합니다.") from exc
    if any(not math.isfinite(radius) or radius <= 0 for radius in radii):
        raise ValueError("radii_km는 0보다 큰 유한한 숫자여야 합니다.")

    raw_regions = payload.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("regions는 하나 이상의 지역 배열이어야 합니다.")
    if not all(isinstance(region, dict) for region in raw_regions):
        raise ValueError("regions의 각 항목은 객체여야 합니다.")
    regions = tuple(BenchmarkRegion.from_dict(region) for region in raw_regions)
    region_names = [region.region_name for region in regions]
    if len(region_names) != len(set(region_names)):
        raise ValueError("regions에 중복된 region_name이 있습니다.")

    return BenchmarkConfig(
        benchmark_name=benchmark_name,
        base_year_month=base_year_month,
        anchor_count_per_region=anchor_count,
        hub_category_large=hub_category_large,
        excluded_hub_category_middle=excluded_middle,
        radii_km=radii,
        regions=regions,
        hub_category_middle=hub_category_middle,
        output_slug=output_slug,
    )


def validate_tour_region_codes(
    regions: tuple[BenchmarkRegion, ...],
    codes_by_area: dict[str, dict[str, str]],
) -> tuple[str, ...]:
    """설정한 KorService2 코드가 공식 코드명과 일치하는지 확인한다."""
    errors: list[str] = []
    for region in regions:
        area_codes = codes_by_area.get(region.tour_area_code, {})
        actual_name = area_codes.get(region.tour_sigungu_code)
        if actual_name == region.tour_sigungu_name:
            continue
        if actual_name is None:
            detail = "존재하지 않는 코드"
        else:
            detail = f"실제 코드명 '{actual_name}'"
        matching_codes = [
            code
            for code, name in area_codes.items()
            if name == region.tour_sigungu_name
        ]
        suggestion = (
            f", 예상 코드 {matching_codes[0]}"
            if len(matching_codes) == 1
            else ""
        )
        errors.append(
            f"{region.region_name}: {region.tour_area_code}/"
            f"{region.tour_sigungu_code}은 {detail}{suggestion}"
        )
    return tuple(errors)


def build_distributions(
    region_results: tuple[BenchmarkRegionResult, ...],
    *,
    radii_km: tuple[float, ...],
    decimal_places: int = 4,
) -> tuple[BenchmarkMetricDistribution, ...]:
    samples = [
        (result, anchor)
        for result in region_results
        for anchor in result.report.anchors
    ]
    group_specs: list[
        tuple[str, str, list[tuple[BenchmarkRegionResult, Any]]]
    ] = [("overall", _overall_group_name(region_results), samples)]
    sample_groups = sorted(
        {result.definition.sample_group for result in region_results}
    )
    for group_name in sample_groups:
        group_specs.append(
            (
                "sampling_stratum",
                group_name,
                [
                    sample
                    for sample in samples
                    if sample[0].definition.sample_group == group_name
                ],
            )
        )
    actual_categories = sorted(
        {anchor.category_middle or "미분류" for _, anchor in samples}
    )
    for category_name in actual_categories:
        group_specs.append(
            (
                "hub_category_middle",
                category_name,
                [
                    sample
                    for sample in samples
                    if (sample[1].category_middle or "미분류")
                    == category_name
                ],
            )
        )

    distributions: list[BenchmarkMetricDistribution] = []

    for grouping_dimension, group_name, selected_samples in group_specs:
        for radius in radii_km:
            values_by_metric = {key: [] for key in BENCHMARK_METRIC_KEYS}
            for _, anchor in selected_samples:
                radius_result = next(
                    item for item in anchor.radii if item.radius_km == radius
                )
                counts = {
                    count.key: float(count.count)
                    for count in radius_result.counts
                }
                for key in BENCHMARK_METRIC_KEYS[:5]:
                    values_by_metric[key].append(counts[key])
                values_by_metric["total_complement_count"].append(
                    float(radius_result.total_complement_count)
                )
                values_by_metric["complement_coverage_score"].append(
                    radius_result.complement_coverage_score
                )

            for metric_key in BENCHMARK_METRIC_KEYS:
                values = values_by_metric[metric_key]
                if not values:
                    continue
                zero_count = sum(value == 0 for value in values)
                distributions.append(
                    BenchmarkMetricDistribution(
                        grouping_dimension=grouping_dimension,
                        group_name=group_name,
                        radius_km=radius,
                        metric_key=metric_key,
                        sample_count=len(values),
                        zero_count=zero_count,
                        zero_rate_percentage=round(
                            zero_count / len(values) * 100,
                            decimal_places,
                        ),
                        minimum=round(min(values), decimal_places),
                        median=round(_percentile(values, 0.5), decimal_places),
                        p75=round(_percentile(values, 0.75), decimal_places),
                        maximum=round(max(values), decimal_places),
                    )
                )
    return tuple(distributions)


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("백분위수를 계산할 값이 없습니다.")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    fraction = position - lower_index
    return (
        ordered[lower_index] * (1 - fraction)
        + ordered[upper_index] * fraction
    )


def _overall_group_name(
    region_results: tuple[BenchmarkRegionResult, ...],
) -> str:
    provinces = {item.definition.province_name for item in region_results}
    return f"{provinces.pop()} 전체" if len(provinces) == 1 else "전체 비교지역"
