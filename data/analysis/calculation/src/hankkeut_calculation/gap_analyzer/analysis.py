"""관광자원 포트폴리오 분석 로직."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from .content_types import CONTENT_TYPES, content_type_name
from .models import PortfolioMetric, PortfolioReport, TourismResource


def analyze_portfolio(
    resources: Iterable[TourismResource],
    *,
    region_name: str,
    area_code: str,
    sigungu_code: str | None,
    area_square_km: float,
    decimal_places: int = 4,
) -> PortfolioReport:
    """관광자원 구성비와 단위면적당 개수를 계산한다.

    구성비는 전체 TourAPI 등록 관광자원에서 각 콘텐츠 유형이 차지하는
    비율이다. 단위면적당 개수는 행정구역 전체 면적(km²)을 분모로 사용한다.
    """
    if area_square_km <= 0:
        raise ValueError("area_square_km는 0보다 커야 합니다.")
    if decimal_places < 0:
        raise ValueError("decimal_places는 0 이상이어야 합니다.")

    resource_list = list(resources)
    counts = Counter(resource.content_type_id for resource in resource_list)
    total = len(resource_list)

    # 표준 유형은 0건이어도 모두 출력하고, API에 새 유형이 추가되거나 유형이
    # 비어 있는 데이터가 오면 뒤에 별도 행으로 보존한다.
    ordered_type_ids: list[int | None] = list(CONTENT_TYPES)
    extra_type_ids = sorted(
        (type_id for type_id in counts if type_id not in CONTENT_TYPES and type_id is not None)
    )
    ordered_type_ids.extend(extra_type_ids)
    if None in counts:
        ordered_type_ids.append(None)

    metrics = tuple(
        _build_metric(
            content_type_id=content_type_id,
            count=counts[content_type_id],
            total=total,
            area_square_km=area_square_km,
            decimal_places=decimal_places,
        )
        for content_type_id in ordered_type_ids
    )

    return PortfolioReport(
        region_name=region_name,
        area_code=str(area_code),
        sigungu_code="" if sigungu_code is None else str(sigungu_code),
        area_square_km=area_square_km,
        total_resource_count=total,
        total_count_per_square_km=round(total / area_square_km, decimal_places),
        metrics=metrics,
    )


def _build_metric(
    *,
    content_type_id: int | None,
    count: int,
    total: int,
    area_square_km: float,
    decimal_places: int,
) -> PortfolioMetric:
    percentage = (count / total * 100) if total else 0.0
    return PortfolioMetric(
        content_type_id=content_type_id,
        content_type_name=content_type_name(content_type_id),
        count=count,
        percentage=round(percentage, decimal_places),
        count_per_square_km=round(count / area_square_km, decimal_places),
    )
