"""지역 관광 보고서."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import CurrentUser, RegionIdPath
from ..schemas.reports import RegionReport
from ..services import report as report_service

router = APIRouter(prefix="/regions", tags=["reports"])
api_v1_router = APIRouter(prefix="/api/v1/regions", tags=["reports"])


@router.get(
    "/{region_id}/report",
    response_model=RegionReport,
    summary="지역 관광 보고서",
)
def get_report(region_id: RegionIdPath, _: CurrentUser) -> RegionReport:
    """유형별 공급 빈칸 진단과 그 근거.

    상세 산출물이 아직 없는 지역은 `INSUFFICIENT_DATA` 준비 중 보고서를
    반환한다. 존재하지 않는 region_id만 404다.
    """
    return RegionReport.model_validate(report_service.build_region_report(region_id))


@api_v1_router.get(
    "/{region_id}/report",
    response_model=RegionReport,
    summary="지역 관광 보고서",
)
def get_v1_report(region_id: RegionIdPath, _: CurrentUser) -> RegionReport:
    """Canonical v1 route; ``tourism-report`` remains a compatibility alias."""
    return RegionReport.model_validate(report_service.build_region_report(region_id))


@api_v1_router.get(
    "/{region_id}/tourism-report",
    response_model=RegionReport,
    summary="지역 관광 보고서",
)
def get_tourism_report(region_id: RegionIdPath, _: CurrentUser) -> RegionReport:
    """Frontend DTO endpoint; the legacy ``/regions/{id}/report`` remains supported."""
    return RegionReport.model_validate(report_service.build_region_report(region_id))
