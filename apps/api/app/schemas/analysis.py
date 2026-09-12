"""관광자원 공급·성과·공백 응답."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import ContentType, RegionRef


# ---------------------------------------------------------------------------
# 콘텐츠 포트폴리오 (TourAPI 8유형)
# ---------------------------------------------------------------------------
class PortfolioMetric(BaseModel):
    content_type_id: int | None = Field(examples=[12])
    content_type_name: str = Field(examples=["관광지"])
    count: int = Field(examples=[412])
    percentage: float = Field(examples=[24.13])
    count_per_square_km: float = Field(examples=[0.3111])


class PortfolioReport(BaseModel):
    """관광자원 포트폴리오."""

    region_name: str = Field(examples=["경주시"])
    area_code: str = Field(examples=["35"])
    sigungu_code: str = Field(examples=["2"])
    area_square_km: float = Field(gt=0, examples=[1324.39])
    total_resource_count: int = Field(examples=[1707])
    total_count_per_square_km: float = Field(examples=[1.2889])
    metrics: list[PortfolioMetric]


# ---------------------------------------------------------------------------
# 중심 관광지
# ---------------------------------------------------------------------------
class HubTouristSpot(BaseModel):
    rank: int = Field(ge=1, examples=[1])
    tourist_spot_code: str = Field(examples=["A0202"])
    name: str = Field(examples=["불국사"])
    category_large: str = Field(default="", examples=["역사관광"])
    category_middle: str = Field(default="", examples=["유적지"])
    category_small: str = Field(default="", examples=["사찰"])
    longitude: float | None = Field(default=None, examples=[129.3320])
    latitude: float | None = Field(default=None, examples=[35.7900])


class HubReport(BaseModel):
    region_name: str = Field(examples=["경주시"])
    base_year_month: str = Field(pattern=r"^\d{6}$", examples=["202606"])
    area_code: str = Field(examples=["35"])
    sigungu_code: str = Field(examples=["2"])
    limit: int = Field(examples=[5])
    extracted_count: int = Field(examples=[5])
    spots: list[HubTouristSpot]


# ---------------------------------------------------------------------------
# 성과 평가
# ---------------------------------------------------------------------------
class PerformanceDataQuality(BaseModel):
    """산출하지 못한 지표와 그 이유."""

    unavailable_metrics: list[str] = Field(examples=[[]])
    note: str = Field(
        examples=["해당 기준연월에 값이 없어 산출하지 않은 지표입니다. 결측은 0으로 채우지 않습니다."]
    )


class PerformanceScore(BaseModel):
    """관광 성과 점수."""

    region_name: str = Field(examples=["경주시"])
    analysis_period: str = Field(examples=["20250101~20251231"])
    visitor_sum: float | None = Field(default=None, examples=[41537820.0])
    resource_demand: float | None = Field(default=None, examples=[None])
    demand_intensity: float | None = Field(default=None, examples=[None])
    visitor_percentile: float | None = Field(default=None, examples=[0.9612])
    resource_demand_percentile: float | None = Field(default=None, examples=[None])
    demand_intensity_percentile: float | None = Field(default=None, examples=[None])
    composite_score: float | None = Field(default=None, examples=[0.9612])
    data_quality: PerformanceDataQuality


# ---------------------------------------------------------------------------
# 관광 공백
# ---------------------------------------------------------------------------
class PeerSupplyComparison(BaseModel):
    peer_region: str = Field(examples=["포항시"])
    peer_composition_share: float = Field(examples=[0.1842])
    peer_density_per_100_km2: float = Field(examples=[31.44])
    target_to_peer_composition_ratio: float | None = Field(default=None, examples=[0.7123])
    target_to_peer_density_ratio: float | None = Field(default=None, examples=[0.6480])
    is_target_composition_lower: bool = Field(examples=[True])
    is_target_density_lower: bool = Field(examples=[True])
    is_relative_supply_gap_candidate: bool = Field(examples=[True])


class ContentTypeComparison(BaseModel):
    content_type: ContentType = Field(examples=["EXPERIENCE_TOURISM"])
    target_place_count: int = Field(examples=[87])
    target_composition_share: float = Field(examples=[0.1312])
    target_density_per_100_km2: float = Field(examples=[20.37])
    individual_peer_comparisons: list[PeerSupplyComparison]
    candidate_peer_regions: list[str] = Field(examples=[["포항시", "서산시"]])
    candidate_peer_count: int = Field(examples=[2])
    lowest_target_to_peer_supply_ratio: float | None = Field(default=None, examples=[0.6480])


class RelativeSupplyReport(BaseModel):
    """Peer 대비 상대적 공급 비교."""

    analysis_type: str = Field(default="relative_supply_gap_by_individual_peer")
    status: str = Field(examples=["provisional"])
    target_region: RegionRef
    peer_regions: list[RegionRef]
    comparison_rule: str = Field(
        examples=[
            "각 Peer와 비교해 유형별 공급 구성비 또는 100㎢당 공급밀도가 낮으면 "
            "상대적 빈칸 후보로 표시합니다."
        ]
    )
    content_type_comparisons: list[ContentTypeComparison]
    priority_order_by_relative_supply_gap: list[ContentType] = Field(
        examples=[["EXPERIENCE_TOURISM", "SHOPPING"]]
    )
    limitations: list[str]


class SupplyPressureMetric(BaseModel):
    content_type: ContentType = Field(examples=["EXPERIENCE_TOURISM"])
    navigation_search_count: int = Field(examples=[184230])
    kakao_supply_place_count: int = Field(gt=0, examples=[87])
    searches_per_place: float = Field(
        examples=[2117.5862], description="목적지 검색량 ÷ 카카오맵 장소 수"
    )


class AnalysisPeriod(BaseModel):
    selection: str = Field(examples=["latest_available_months"])
    month_count: int = Field(examples=[12])
    start_ym: str = Field(pattern=r"^\d{6}$", examples=["202508"])
    end_ym: str = Field(pattern=r"^\d{6}$", examples=["202607"])


class SupplyPressureReport(BaseModel):
    """유형별 공급 압력."""

    report_version: str = Field(examples=["2026-09-05"])
    region_name: str = Field(examples=["경주시"])
    analysis_period: AnalysisPeriod
    metric_definition: str = Field(
        examples=["유형별 내비게이션 목적지 검색량 ÷ 카카오맵 유형별 장소 수"]
    )
    content_type_metrics: list[SupplyPressureMetric]
    priority_order_by_supply_pressure: list[ContentType] = Field(
        examples=[["EXPERIENCE_TOURISM", "ACCOMMODATION"]]
    )
    warnings: list[str]


class GapReport(BaseModel):
    """관광 콘텐츠 공백 진단."""

    target: RegionRef
    relative_supply: RelativeSupplyReport
    supply_pressure: SupplyPressureReport
