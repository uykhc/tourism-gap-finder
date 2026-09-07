"""관광 공급·성과·공백 분석."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import examples
from ..deps import RegionIdPath
from ..schemas.analysis import GapReport, HubReport, PerformanceScore, PortfolioReport

router = APIRouter(prefix="/regions", tags=["analysis"])


@router.get(
    "/{region_id}/portfolio",
    response_model=PortfolioReport,
    summary="관광자원 포트폴리오",
)
def get_portfolio(region_id: RegionIdPath) -> PortfolioReport:
    """콘텐츠 유형별 개수·구성비·단위면적당 밀도."""
    # TODO(실연결): gap_analyzer.tour_api.TourApiClient 로 자원을 받아
    #   gap_analyzer.analysis.analyze_portfolio() 에 넘긴다. TourAPI 키 필요.
    del region_id
    return PortfolioReport.model_validate(examples.portfolio_report())


@router.get("/{region_id}/hubs", response_model=HubReport, summary="중심 관광지 상위 N")
def get_hubs(
    region_id: RegionIdPath,
    base_year_month: str = Query(
        default="202606", pattern=r"^\d{6}$", description="기준연월 YYYYMM"
    ),
    limit: int = Query(default=5, ge=1, le=20),
) -> HubReport:
    """기초지자체 중심 관광지 상위 목록."""
    # TODO(실연결): gap_analyzer.hub_api.HubTourApiClient. HUB_TOUR_API_SERVICE_KEY 필요.
    del region_id
    return HubReport.model_validate(
        {**examples.HUB_REPORT, "base_year_month": base_year_month, "limit": limit}
    )


@router.get(
    "/{region_id}/performance",
    response_model=PerformanceScore,
    summary="관광 성과 점수",
)
def get_performance(region_id: RegionIdPath) -> PerformanceScore:
    """이동통신 기반 방문자 수 기준 성과 점수.

    산출 불가한 지표는 `data_quality.unavailable_metrics`에 담긴다.
    """
    # TODO(실연결): performance_evaluator.visitor_portfolio_benchmark 의
    #   aggregate_daily_visitor_sums + build_city_tourism_scores.
    del region_id
    return PerformanceScore.model_validate(examples.PERFORMANCE_SCORE)


@router.get("/{region_id}/gaps", response_model=GapReport, summary="관광 콘텐츠 공백")
def get_gaps(
    region_id: RegionIdPath,
    peer_count: int = Query(default=3, ge=1, le=5, description="비교에 쓸 상위 Peer 수"),
) -> GapReport:
    """Peer 대비 상대적 공급 부족과 수요 대비 공급 압력."""
    # TODO(실연결): datalab_navigation.relative_supply.build_relative_supply_report +
    #   navigation_demand.build_supply_pressure_report.
    #   공급압력은 데이터랩 CSV 수동 다운로드가 선행돼야 한다.
    del region_id, peer_count
    return GapReport.model_validate(examples.gap_report())
