"""관광 공급·성과·공백 분석."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import examples
from ..services import artifacts
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
    # TODO(실연결): hankkeut_calculation.gap_analyzer.tour_api.TourApiClient 로
    #   자원을 받아 gap_analyzer.analysis.analyze_portfolio() 에 넘긴다.
    #   KOR_TOUR_API_SERVICE_KEY 가 없으면 503으로 명확히 실패시킨다 (mock 금지).
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
    # TODO(실연결): hankkeut_calculation.gap_analyzer.hub_api.HubTourApiClient.
    #   HUB_TOUR_API_SERVICE_KEY 가 없으면 503 (mock 금지).
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
    # TODO(실연결): hankkeut_evaluation.visitor_portfolio_benchmark 의
    #   aggregate_daily_visitor_sums + build_regional_tourism_scores.
    #   백분위는 비교 집단이 있어야 의미가 있으므로 대상 + peer 집합으로 계산한다.
    #   TourAPI 코드는 services.regions.tour_api_code() 로 얻는다.
    del region_id
    return PerformanceScore.model_validate(examples.PERFORMANCE_SCORE)


@router.get("/{region_id}/gaps", response_model=GapReport, summary="관광 콘텐츠 공백")
def get_gaps(
    region_id: RegionIdPath,
    peer_count: int = Query(default=3, ge=1, le=5, description="비교에 쓸 상위 Peer 수"),
) -> GapReport:
    """Peer 대비 상대적 공급 부족과 수요 대비 공급 압력."""
    # `peer_count` is a request-time display limit.  The persisted analysis
    # retains the exact peers that were used when the job ran.
    del peer_count
    return GapReport.model_validate(artifacts.gaps(region_id))
