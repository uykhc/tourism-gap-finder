"""관광 공급·성과·공백 분석."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..services import artifacts
from ..deps import CurrentUser, RegionIdPath
from ..schemas.analysis import GapReport, HubReport, PerformanceScore, PortfolioReport

router = APIRouter(prefix="/regions", tags=["analysis"])


@router.get(
    "/{region_id}/portfolio",
    response_model=PortfolioReport,
    summary="관광자원 포트폴리오",
)
def get_portfolio(region_id: RegionIdPath, _: CurrentUser) -> PortfolioReport:
    """콘텐츠 유형별 개수·구성비·단위면적당 밀도."""
    return PortfolioReport.model_validate(artifacts.portfolio_report(region_id))


@router.get("/{region_id}/hubs", response_model=HubReport, summary="중심 관광지 상위 N")
def get_hubs(
    region_id: RegionIdPath,
    _: CurrentUser,
    base_year_month: str | None = Query(
        default=None,
        pattern=r"^\d{6}$",
        description="기준연월 YYYYMM. 생략하면 활성 릴리스의 기준월",
    ),
    limit: int = Query(default=5, ge=1, le=20),
) -> HubReport:
    """기초지자체 중심 관광지 상위 목록."""
    return HubReport.model_validate(
        artifacts.hub_report(region_id, base_year_month=base_year_month, limit=limit)
    )


@router.get(
    "/{region_id}/performance",
    response_model=PerformanceScore,
    summary="관광 성과 점수",
)
def get_performance(region_id: RegionIdPath, _: CurrentUser) -> PerformanceScore:
    """이동통신 기반 방문자 수 기준 성과 점수.

    산출 불가한 지표는 `data_quality.unavailable_metrics`에 담긴다.
    """
    return PerformanceScore.model_validate(artifacts.performance_score(region_id))


@router.get("/{region_id}/gaps", response_model=GapReport, summary="관광 콘텐츠 공백")
def get_gaps(
    region_id: RegionIdPath,
    _: CurrentUser,
    peer_count: int = Query(default=3, ge=1, le=5, description="비교에 쓸 상위 Peer 수"),
) -> GapReport:
    """Peer 대비 상대적 공급 부족과 수요 대비 공급 압력."""
    # `peer_count` is a request-time display limit.  The persisted analysis
    # retains the exact peers that were used when the job ran.
    del peer_count
    return GapReport.model_validate(artifacts.gaps(region_id))
