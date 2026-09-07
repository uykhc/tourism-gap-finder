"""분석에서 사용하는 도메인 모델."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TourismResource:
    """TourAPI에서 수집한 관광자원 한 건."""

    content_id: str
    content_type_id: int | None
    title: str = ""
    address: str = ""
    longitude: float | None = None
    latitude: float | None = None


@dataclass(frozen=True, slots=True)
class HubTouristSpot:
    """기초지자체 중심 관광지 API에서 조회한 관광지 한 건."""

    rank: int
    tourist_spot_code: str
    name: str
    category_large: str = ""
    category_middle: str = ""
    category_small: str = ""
    longitude: float | None = None
    latitude: float | None = None
    raw_fields: dict[str, Any] = field(default_factory=dict, repr=False)

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
            "raw_fields": dict(self.raw_fields),
        }


@dataclass(frozen=True, slots=True)
class HubTouristSpotReport:
    """한 기초지자체의 중심 관광지 상위 목록."""

    region_name: str
    base_year_month: str
    area_code: str
    sigungu_code: str
    limit: int
    spots: tuple[HubTouristSpot, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "base_year_month": self.base_year_month,
            "area_code": self.area_code,
            "sigungu_code": self.sigungu_code,
            "limit": self.limit,
            "extracted_count": len(self.spots),
            "spots": [spot.to_dict() for spot in self.spots],
        }


@dataclass(frozen=True, slots=True)
class PortfolioMetric:
    """콘텐츠 유형 하나의 포트폴리오 지표."""

    content_type_id: int | None
    content_type_name: str
    count: int
    percentage: float
    count_per_square_km: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PortfolioReport:
    """시군구 하나의 관광자원 포트폴리오 분석 결과."""

    region_name: str
    area_code: str
    sigungu_code: str
    area_square_km: float
    total_resource_count: int
    total_count_per_square_km: float
    metrics: tuple[PortfolioMetric, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "area_code": self.area_code,
            "sigungu_code": self.sigungu_code,
            "area_square_km": self.area_square_km,
            "total_resource_count": self.total_resource_count,
            "total_count_per_square_km": self.total_count_per_square_km,
            "metrics": [metric.to_dict() for metric in self.metrics],
        }
