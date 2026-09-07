"""시군구 관광자원 포트폴리오 밀도 벤치마크."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hankkeut_calculation.gap_analyzer.content_types import CONTENT_TYPES
from hankkeut_calculation.gap_analyzer.models import PortfolioMetric, PortfolioReport

ADMINISTRATIVE_TYPES = {
    "city": "시",
    "county": "군",
    "urban_district": "도시 자치구",
}


@dataclass(frozen=True, slots=True)
class PortfolioBenchmarkRegion:
    region_name: str
    province_name: str
    administrative_type: str
    area_code: str
    sigungu_code: str
    area_square_km: float

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PortfolioBenchmarkRegion":
        required = (
            "region_name",
            "province_name",
            "administrative_type",
            "area_code",
            "sigungu_code",
        )
        missing = [key for key in required if not str(value.get(key, "")).strip()]
        if missing:
            raise ValueError("지역 설정 필수 항목 누락: " + ", ".join(missing))
        administrative_type = str(value["administrative_type"]).strip()
        if administrative_type not in ADMINISTRATIVE_TYPES:
            raise ValueError(
                "administrative_type은 city, county, urban_district 중 "
                "하나여야 합니다."
            )
        try:
            area_square_km = float(value["area_square_km"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("area_square_km는 숫자여야 합니다.") from exc
        if not math.isfinite(area_square_km) or area_square_km <= 0:
            raise ValueError("area_square_km는 0보다 큰 유한한 숫자여야 합니다.")
        return cls(
            region_name=str(value["region_name"]).strip(),
            province_name=str(value["province_name"]).strip(),
            administrative_type=administrative_type,
            area_code=str(value["area_code"]).strip(),
            sigungu_code=str(value["sigungu_code"]).strip(),
            area_square_km=area_square_km,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "province_name": self.province_name,
            "administrative_type": self.administrative_type,
            "administrative_type_name": ADMINISTRATIVE_TYPES[
                self.administrative_type
            ],
            "area_code": self.area_code,
            "sigungu_code": self.sigungu_code,
            "area_square_km": self.area_square_km,
        }


@dataclass(frozen=True, slots=True)
class PortfolioBenchmarkConfig:
    benchmark_name: str
    output_slug: str
    area_reference_date: str
    area_source_url: str
    regions: tuple[PortfolioBenchmarkRegion, ...]


@dataclass(frozen=True, slots=True)
class PortfolioBenchmarkRegionResult:
    definition: PortfolioBenchmarkRegion
    report: PortfolioReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition": self.definition.to_dict(),
            "report": self.report.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PortfolioDensityDistribution:
    grouping_dimension: str
    group_name: str
    content_type_id: int
    content_type_name: str
    sample_count: int
    zero_count: int
    zero_rate_percentage: float
    density_minimum: float
    density_median: float
    density_p75: float
    density_maximum: float
    count_median: float
    percentage_median: float

    def to_dict(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in self.__dataclass_fields__
        }


@dataclass(frozen=True, slots=True)
class PortfolioBenchmarkRunReport:
    benchmark_name: str
    output_slug: str
    generated_at: str
    area_reference_date: str
    area_source_url: str
    region_results: tuple[PortfolioBenchmarkRegionResult, ...]
    distributions: tuple[PortfolioDensityDistribution, ...]
    failures: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_name": self.benchmark_name,
            "output_slug": self.output_slug,
            "generated_at": self.generated_at,
            "area_reference_date": self.area_reference_date,
            "area_source_url": self.area_source_url,
            "successful_region_count": len(self.region_results),
            "failed_region_count": len(self.failures),
            "region_results": [item.to_dict() for item in self.region_results],
            "distributions": [item.to_dict() for item in self.distributions],
            "failures": [
                {"region_name": name, "error": error}
                for name, error in self.failures
            ],
        }


def load_portfolio_benchmark_config(path: Path) -> PortfolioBenchmarkConfig:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"포트폴리오 벤치마크 설정 파일이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"설정 JSON 형식이 올바르지 않습니다: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("설정 JSON 최상위 값은 객체여야 합니다.")

    benchmark_name = str(payload.get("benchmark_name", "")).strip()
    output_slug = str(payload.get("output_slug", "")).strip()
    area_reference_date = str(payload.get("area_reference_date", "")).strip()
    area_source_url = str(payload.get("area_source_url", "")).strip()
    if not benchmark_name:
        raise ValueError("benchmark_name이 비어 있습니다.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", output_slug):
        raise ValueError("output_slug 형식이 올바르지 않습니다.")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", area_reference_date):
        raise ValueError("area_reference_date는 YYYY-MM-DD 형식이어야 합니다.")
    if not area_source_url.startswith("https://"):
        raise ValueError("area_source_url은 https:// 주소여야 합니다.")

    raw_regions = payload.get("regions")
    if not isinstance(raw_regions, list) or not raw_regions:
        raise ValueError("regions는 하나 이상의 지역 배열이어야 합니다.")
    if not all(isinstance(item, dict) for item in raw_regions):
        raise ValueError("regions의 각 항목은 객체여야 합니다.")
    regions = tuple(PortfolioBenchmarkRegion.from_dict(item) for item in raw_regions)
    names = [f"{item.province_name} {item.region_name}" for item in regions]
    codes = [(item.area_code, item.sigungu_code) for item in regions]
    if len(names) != len(set(names)):
        raise ValueError("regions에 중복된 지역명이 있습니다.")
    if len(codes) != len(set(codes)):
        raise ValueError("regions에 중복된 TourAPI 코드가 있습니다.")
    return PortfolioBenchmarkConfig(
        benchmark_name=benchmark_name,
        output_slug=output_slug,
        area_reference_date=area_reference_date,
        area_source_url=area_source_url,
        regions=regions,
    )


def validate_portfolio_region_codes(
    regions: tuple[PortfolioBenchmarkRegion, ...],
    codes_by_area: dict[str, dict[str, str]],
) -> tuple[str, ...]:
    errors: list[str] = []
    for region in regions:
        actual = codes_by_area.get(region.area_code, {}).get(region.sigungu_code)
        if actual == region.region_name:
            continue
        matches = [
            code
            for code, name in codes_by_area.get(region.area_code, {}).items()
            if name == region.region_name
        ]
        suggestion = f", 예상 코드 {matches[0]}" if len(matches) == 1 else ""
        detail = "존재하지 않는 코드" if actual is None else f"실제 코드명 '{actual}'"
        errors.append(
            f"{region.province_name} {region.region_name}: "
            f"{region.area_code}/{region.sigungu_code}은 {detail}{suggestion}"
        )
    return tuple(errors)


def portfolio_region_result_from_dict(
    value: dict[str, Any],
) -> PortfolioBenchmarkRegionResult:
    """저장된 벤치마크 JSON의 지역 결과를 도메인 모델로 복원한다."""
    try:
        definition = PortfolioBenchmarkRegion.from_dict(value["definition"])
        raw_report = value["report"]
        metrics = tuple(PortfolioMetric(**item) for item in raw_report["metrics"])
        report = PortfolioReport(
            region_name=str(raw_report["region_name"]),
            area_code=str(raw_report["area_code"]),
            sigungu_code=str(raw_report["sigungu_code"]),
            area_square_km=float(raw_report["area_square_km"]),
            total_resource_count=int(raw_report["total_resource_count"]),
            total_count_per_square_km=float(
                raw_report["total_count_per_square_km"]
            ),
            metrics=metrics,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("저장된 포트폴리오 지역 결과 형식이 올바르지 않습니다.") from exc
    return PortfolioBenchmarkRegionResult(definition=definition, report=report)


def build_portfolio_distributions(
    region_results: tuple[PortfolioBenchmarkRegionResult, ...],
    *,
    decimal_places: int = 6,
) -> tuple[PortfolioDensityDistribution, ...]:
    group_specs = [("overall", _overall_group_name(region_results), list(region_results))]
    for key, name in ADMINISTRATIVE_TYPES.items():
        group_specs.append(
            (
                "administrative_type",
                name,
                [item for item in region_results if item.definition.administrative_type == key],
            )
        )

    distributions: list[PortfolioDensityDistribution] = []
    for dimension, group_name, selected in group_specs:
        if not selected:
            continue
        for content_type_id, content_type_name in CONTENT_TYPES.items():
            samples = []
            for item in selected:
                metric = next(
                    metric
                    for metric in item.report.metrics
                    if metric.content_type_id == content_type_id
                )
                exact_density = metric.count / item.definition.area_square_km
                exact_percentage = (
                    metric.count / item.report.total_resource_count * 100
                    if item.report.total_resource_count
                    else 0.0
                )
                samples.append((metric.count, exact_density, exact_percentage))
            counts = [float(sample[0]) for sample in samples]
            densities = [sample[1] for sample in samples]
            percentages = [sample[2] for sample in samples]
            zero_count = sum(count == 0 for count in counts)
            distributions.append(
                PortfolioDensityDistribution(
                    grouping_dimension=dimension,
                    group_name=group_name,
                    content_type_id=content_type_id,
                    content_type_name=content_type_name,
                    sample_count=len(samples),
                    zero_count=zero_count,
                    zero_rate_percentage=round(zero_count / len(samples) * 100, 4),
                    density_minimum=round(min(densities), decimal_places),
                    density_median=round(_percentile(densities, 0.5), decimal_places),
                    density_p75=round(_percentile(densities, 0.75), decimal_places),
                    density_maximum=round(max(densities), decimal_places),
                    count_median=round(_percentile(counts, 0.5), 4),
                    percentage_median=round(_percentile(percentages, 0.5), 4),
                )
            )
    return tuple(distributions)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _overall_group_name(
    region_results: tuple[PortfolioBenchmarkRegionResult, ...],
) -> str:
    """동일 시도 설정이면 해당 시도명을, 혼합 설정이면 일반 이름을 쓴다."""
    provinces = {item.definition.province_name for item in region_results}
    return f"{provinces.pop()} 전체" if len(provinces) == 1 else "전체 비교지역"
