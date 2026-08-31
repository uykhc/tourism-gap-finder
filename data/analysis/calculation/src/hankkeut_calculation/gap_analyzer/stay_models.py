"""체류 전환 빈칸 분석 결과 모델."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StayComplementCount:
    """체류 보완 유형 하나의 반경 내 자원 수."""

    key: str
    content_type_id: int
    name: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "content_type_id": self.content_type_id,
            "name": self.name,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class StayRadiusResult:
    """대표 관광지 하나의 특정 반경 분석 결과."""

    radius_km: float
    counts: tuple[StayComplementCount, ...]
    total_complement_count: int
    covered_type_count: int
    complement_coverage_score: float
    missing_type_names: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "radius_km": self.radius_km,
            "counts": [count.to_dict() for count in self.counts],
            "total_complement_count": self.total_complement_count,
            "covered_type_count": self.covered_type_count,
            "complement_coverage_score": self.complement_coverage_score,
            "missing_type_names": list(self.missing_type_names),
        }


@dataclass(frozen=True, slots=True)
class StayAnchorResult:
    """대표 관광지 하나의 체류 보완 분석 결과."""

    rank: int
    tourist_spot_code: str
    name: str
    category_large: str
    category_middle: str
    category_small: str
    longitude: float
    latitude: float
    radii: tuple[StayRadiusResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "tourist_spot_code": self.tourist_spot_code,
            "name": self.name,
            "category_large": self.category_large,
            "category_middle": self.category_middle,
            "category_small": self.category_small,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "radii": [radius.to_dict() for radius in self.radii],
        }


@dataclass(frozen=True, slots=True)
class StayRegionalSummary:
    """특정 반경에서 대표 관광지 전체를 요약한 결과."""

    radius_km: float
    anchor_count: int
    average_counts: tuple[tuple[str, float], ...]
    average_total_complement_count: float
    average_complement_coverage_score: float
    unique_complement_resource_count: int
    anchor_resource_occurrence_count: int
    overlap_occurrence_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "radius_km": self.radius_km,
            "anchor_count": self.anchor_count,
            "average_counts": dict(self.average_counts),
            "average_total_complement_count": (
                self.average_total_complement_count
            ),
            "average_complement_coverage_score": (
                self.average_complement_coverage_score
            ),
            "unique_complement_resource_count": (
                self.unique_complement_resource_count
            ),
            "anchor_resource_occurrence_count": (
                self.anchor_resource_occurrence_count
            ),
            "overlap_occurrence_count": self.overlap_occurrence_count,
        }


@dataclass(frozen=True, slots=True)
class StayTransitionReport:
    """기초지자체 하나의 체류 전환 빈칸 분석 보고서."""

    region_name: str
    generated_at: str
    hub_base_year_month: str
    hub_area_code: str
    hub_sigungu_code: str
    tour_area_code: str
    tour_sigungu_code: str
    requested_anchor_count: int
    analyzed_anchor_count: int
    total_tourism_resource_count: int
    geocoded_tourism_resource_count: int
    score_method: str
    anchors: tuple[StayAnchorResult, ...]
    regional_summaries: tuple[StayRegionalSummary, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "generated_at": self.generated_at,
            "hub_base_year_month": self.hub_base_year_month,
            "hub_area_code": self.hub_area_code,
            "hub_sigungu_code": self.hub_sigungu_code,
            "tour_area_code": self.tour_area_code,
            "tour_sigungu_code": self.tour_sigungu_code,
            "requested_anchor_count": self.requested_anchor_count,
            "analyzed_anchor_count": self.analyzed_anchor_count,
            "total_tourism_resource_count": self.total_tourism_resource_count,
            "geocoded_tourism_resource_count": (
                self.geocoded_tourism_resource_count
            ),
            "score_method": self.score_method,
            "anchors": [anchor.to_dict() for anchor in self.anchors],
            "regional_summaries": [
                summary.to_dict() for summary in self.regional_summaries
            ],
        }
