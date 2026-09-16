"""관광 공급·성과·공백 분석."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import examples
from ..services import analysis_runtime, artifacts
from ..services import regions as region_table
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
    region, features, area_code, sigungu_code = _tour_api_region(region_id)
    service_key = analysis_runtime.require_env(
        "KOR_TOUR_API_SERVICE_KEY",
        "TOUR_API_SERVICE_KEY",
        feature="관광자원 포트폴리오",
    )
    tour_api = analysis_runtime.require_module(
        "hankkeut_calculation.gap_analyzer.tour_api",
        feature="관광자원 포트폴리오",
    )
    portfolio = analysis_runtime.require_module(
        "hankkeut_calculation.gap_analyzer.analysis",
        feature="관광자원 포트폴리오",
    )
    try:
        resources = tour_api.TourApiClient(service_key).fetch_region_resources(
            area_code=area_code,
            sigungu_code=sigungu_code,
        )
    except tour_api.TourApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    report = portfolio.analyze_portfolio(
        resources,
        region_name=region["region_name"],
        area_code=area_code,
        sigungu_code=sigungu_code,
        area_square_km=features["area_km2"],
    )
    return PortfolioReport.model_validate(report.to_dict())


@router.get("/{region_id}/hubs", response_model=HubReport, summary="중심 관광지 상위 N")
def get_hubs(
    region_id: RegionIdPath,
    base_year_month: str = Query(
        default="202606", pattern=r"^\d{6}$", description="기준연월 YYYYMM"
    ),
    limit: int = Query(default=5, ge=1, le=20),
) -> HubReport:
    """기초지자체 중심 관광지 상위 목록."""
    region, _, area_code, sigungu_code = _tour_api_region(region_id)
    service_key = analysis_runtime.require_env(
        "HUB_TOUR_API_SERVICE_KEY",
        "TOUR_API_SERVICE_KEY",
        feature="중심 관광지",
    )
    hub_api = analysis_runtime.require_module(
        "hankkeut_calculation.gap_analyzer.hub_api",
        feature="중심 관광지",
    )
    try:
        spots = hub_api.HubTourApiClient(service_key).fetch_top_spots(
            base_year_month=base_year_month,
            area_code=area_code,
            sigungu_code=sigungu_code,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except hub_api.HubTourApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return HubReport.model_validate(
        {
            "region_name": region["region_name"],
            "base_year_month": base_year_month,
            "area_code": area_code,
            "sigungu_code": sigungu_code,
            "limit": limit,
            "extracted_count": len(spots),
            "spots": [spot.to_dict() for spot in spots],
        }
    )


def _tour_api_region(
    region_id: str,
) -> tuple[dict[str, object], dict[str, float], str, str]:
    """실시간 TourAPI 호출에 필요한 지역 정보와 코드."""
    region = region_table.find_region(region_id)
    features = region_table.find_region_features(region_id)
    if region is None or features is None:
        raise HTTPException(status_code=404, detail=f"Unknown region_id: {region_id}")
    codes = region_table.tour_api_code(region_id)
    if codes is None:
        raise HTTPException(
            status_code=503,
            detail=f"TourAPI 지역 코드가 아직 제공되지 않습니다: {region_id}",
        )
    return region, features, codes[0], codes[1]


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
