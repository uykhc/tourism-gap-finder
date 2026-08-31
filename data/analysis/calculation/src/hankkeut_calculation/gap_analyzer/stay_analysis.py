"""대표 관광지 주변 체류 보완 자원 분석."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

from .models import HubTouristSpot, TourismResource
from .stay_models import (
    StayAnchorResult,
    StayComplementCount,
    StayRadiusResult,
    StayRegionalSummary,
    StayTransitionReport,
)

EARTH_RADIUS_KM = 6371.0088
SCORE_METHOD = (
    "음식점·숙박·문화시설·행사·쇼핑 중 반경 내 1개 이상 존재하는 "
    "유형당 20점(최대 100점)"
)

# 체류 보완 유형의 출력 순서와 JSON/CSV 키를 한 곳에서 관리한다.
STAY_COMPLEMENT_TYPES: tuple[tuple[int, str, str], ...] = (
    (39, "food", "음식점"),
    (32, "accommodation", "숙박"),
    (14, "culture", "문화시설"),
    (15, "event", "행사/공연/축제"),
    (38, "shopping", "쇼핑"),
)
STAY_CONTENT_TYPE_IDS = frozenset(
    content_type_id for content_type_id, _, _ in STAY_COMPLEMENT_TYPES
)


def analyze_stay_transition(
    hubs: Iterable[HubTouristSpot],
    resources: Iterable[TourismResource],
    *,
    region_name: str,
    generated_at: str,
    hub_base_year_month: str,
    hub_area_code: str,
    hub_sigungu_code: str,
    tour_area_code: str,
    tour_sigungu_code: str,
    requested_anchor_count: int = 5,
    radii_km: Iterable[float] = (1.0, 2.0),
    decimal_places: int = 4,
) -> StayTransitionReport:
    """대표 관광지별 체류 보완 유형 수와 지역 요약을 계산한다."""
    radii = _normalize_radii(radii_km)
    if requested_anchor_count <= 0:
        raise ValueError("requested_anchor_count는 0보다 커야 합니다.")
    if decimal_places < 0:
        raise ValueError("decimal_places는 0 이상이어야 합니다.")

    hub_list = list(hubs)
    invalid_hubs = [hub.name or str(hub.rank) for hub in hub_list if not _has_coordinates(hub)]
    if invalid_hubs:
        raise ValueError(
            "좌표가 없는 대표 관광지는 분석할 수 없습니다: "
            + ", ".join(invalid_hubs)
        )

    resource_list = list(resources)
    geocoded_resources = [
        resource for resource in resource_list if _has_coordinates(resource)
    ]
    complement_resources = [
        resource
        for resource in geocoded_resources
        if resource.content_type_id in STAY_CONTENT_TYPE_IDS
    ]

    anchor_results: list[StayAnchorResult] = []
    # 지역 요약의 중복/고유 개수 계산을 위해 반경별 자원 키를 보존한다.
    resource_keys_by_radius: dict[float, list[set[tuple[object, ...]]]] = {
        radius: [] for radius in radii
    }

    for hub in hub_list:
        distances = [
            (resource, haversine_distance_km(hub, resource))
            for resource in complement_resources
        ]
        radius_results: list[StayRadiusResult] = []
        for radius in radii:
            nearby = [
                resource for resource, distance in distances if distance <= radius
            ]
            counts = Counter(resource.content_type_id for resource in nearby)
            metrics = tuple(
                StayComplementCount(
                    key=key,
                    content_type_id=content_type_id,
                    name=name,
                    count=counts[content_type_id],
                )
                for content_type_id, key, name in STAY_COMPLEMENT_TYPES
            )
            covered_type_count = sum(metric.count > 0 for metric in metrics)
            missing_type_names = tuple(
                metric.name for metric in metrics if metric.count == 0
            )
            radius_results.append(
                StayRadiusResult(
                    radius_km=radius,
                    counts=metrics,
                    total_complement_count=len(nearby),
                    covered_type_count=covered_type_count,
                    complement_coverage_score=round(
                        covered_type_count / len(STAY_COMPLEMENT_TYPES) * 100,
                        decimal_places,
                    ),
                    missing_type_names=missing_type_names,
                )
            )
            resource_keys_by_radius[radius].append(
                {_resource_key(resource) for resource in nearby}
            )

        anchor_results.append(
            StayAnchorResult(
                rank=hub.rank,
                tourist_spot_code=hub.tourist_spot_code,
                name=hub.name,
                category_large=hub.category_large,
                category_middle=hub.category_middle,
                category_small=hub.category_small,
                longitude=float(hub.longitude),
                latitude=float(hub.latitude),
                radii=tuple(radius_results),
            )
        )

    regional_summaries = tuple(
        _build_regional_summary(
            radius=radius,
            anchors=anchor_results,
            resource_key_sets=resource_keys_by_radius[radius],
            decimal_places=decimal_places,
        )
        for radius in radii
    )

    return StayTransitionReport(
        region_name=region_name,
        generated_at=generated_at,
        hub_base_year_month=hub_base_year_month,
        hub_area_code=str(hub_area_code),
        hub_sigungu_code=str(hub_sigungu_code),
        tour_area_code=str(tour_area_code),
        tour_sigungu_code=str(tour_sigungu_code),
        requested_anchor_count=requested_anchor_count,
        analyzed_anchor_count=len(anchor_results),
        total_tourism_resource_count=len(resource_list),
        geocoded_tourism_resource_count=len(geocoded_resources),
        score_method=SCORE_METHOD,
        anchors=tuple(anchor_results),
        regional_summaries=regional_summaries,
    )


def haversine_distance_km(
    first: HubTouristSpot | TourismResource,
    second: HubTouristSpot | TourismResource,
) -> float:
    """두 WGS84 좌표 사이의 대권 직선거리를 km로 반환한다."""
    if not _has_coordinates(first) or not _has_coordinates(second):
        raise ValueError("거리 계산에는 두 지점의 위도와 경도가 모두 필요합니다.")

    first_latitude = math.radians(float(first.latitude))
    second_latitude = math.radians(float(second.latitude))
    latitude_delta = second_latitude - first_latitude
    longitude_delta = math.radians(
        float(second.longitude) - float(first.longitude)
    )
    haversine = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(first_latitude)
        * math.cos(second_latitude)
        * math.sin(longitude_delta / 2) ** 2
    )
    # 부동소수점 반올림으로 haversine이 아주 조금 1을 넘는 경우를 방어한다.
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, haversine)))


def _build_regional_summary(
    *,
    radius: float,
    anchors: list[StayAnchorResult],
    resource_key_sets: list[set[tuple[object, ...]]],
    decimal_places: int,
) -> StayRegionalSummary:
    radius_results = [
        next(result for result in anchor.radii if result.radius_km == radius)
        for anchor in anchors
    ]
    anchor_count = len(radius_results)
    if anchor_count:
        average_counts = tuple(
            (
                key,
                round(
                    sum(
                        next(count.count for count in result.counts if count.key == key)
                        for result in radius_results
                    )
                    / anchor_count,
                    decimal_places,
                ),
            )
            for _, key, _ in STAY_COMPLEMENT_TYPES
        )
        average_total = round(
            sum(result.total_complement_count for result in radius_results)
            / anchor_count,
            decimal_places,
        )
        average_score = round(
            sum(result.complement_coverage_score for result in radius_results)
            / anchor_count,
            decimal_places,
        )
    else:
        average_counts = tuple(
            (key, 0.0) for _, key, _ in STAY_COMPLEMENT_TYPES
        )
        average_total = 0.0
        average_score = 0.0

    all_unique_keys: set[tuple[object, ...]] = set()
    for keys in resource_key_sets:
        all_unique_keys.update(keys)
    occurrence_count = sum(len(keys) for keys in resource_key_sets)

    return StayRegionalSummary(
        radius_km=radius,
        anchor_count=anchor_count,
        average_counts=average_counts,
        average_total_complement_count=average_total,
        average_complement_coverage_score=average_score,
        unique_complement_resource_count=len(all_unique_keys),
        anchor_resource_occurrence_count=occurrence_count,
        overlap_occurrence_count=occurrence_count - len(all_unique_keys),
    )


def _normalize_radii(radii_km: Iterable[float]) -> tuple[float, ...]:
    radii = tuple(sorted({float(radius) for radius in radii_km}))
    if not radii:
        raise ValueError("분석 반경을 하나 이상 입력해야 합니다.")
    if any(not math.isfinite(radius) or radius <= 0 for radius in radii):
        raise ValueError("분석 반경은 0보다 큰 유한한 숫자여야 합니다.")
    return radii


def _has_coordinates(value: HubTouristSpot | TourismResource) -> bool:
    if value.longitude is None or value.latitude is None:
        return False
    return (
        math.isfinite(float(value.longitude))
        and math.isfinite(float(value.latitude))
        and -180 <= float(value.longitude) <= 180
        and -90 <= float(value.latitude) <= 90
    )


def _resource_key(resource: TourismResource) -> tuple[object, ...]:
    if resource.content_id:
        return ("content_id", resource.content_id)
    return (
        "fallback",
        resource.content_type_id,
        resource.title,
        resource.longitude,
        resource.latitude,
    )
