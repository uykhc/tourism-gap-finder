"""Typed models for Kakao Local category search results."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class KakaoPlace:
    place_id: str
    name: str
    category_group_code: str
    category_group_name: str
    category_name: str
    address: str
    road_address: str
    longitude: float
    latitude: float
    phone: str
    place_url: str
    distance_meters: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class KakaoCategoryCollection:
    category_group_code: str
    category_group_name: str
    center_longitude: float
    center_latitude: float
    radius_meters: int
    api_total_count: int
    pageable_count: int
    collected_count: int
    result_truncated: bool
    places: tuple[KakaoPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_group_code": self.category_group_code,
            "category_group_name": self.category_group_name,
            "center_longitude": self.center_longitude,
            "center_latitude": self.center_latitude,
            "radius_meters": self.radius_meters,
            "api_total_count": self.api_total_count,
            "pageable_count": self.pageable_count,
            "collected_count": self.collected_count,
            "result_truncated": self.result_truncated,
            "places": [place.to_dict() for place in self.places],
        }


@dataclass(frozen=True, slots=True)
class KakaoCategoryMetadata:
    category_group_code: str
    total_count: int
    pageable_count: int
