"""지역 관광 보고서."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import CurrentUser, RegionIdPath
from ..schemas.reports import RegionReport
from ..services import report as report_service

router = APIRouter(prefix="/regions", tags=["reports"])


@router.get(
    "/{region_id}/report",
    response_model=RegionReport,
    summary="지역 관광 보고서",
)
def get_report(region_id: RegionIdPath, _: CurrentUser) -> RegionReport:
    """유형별 공급 빈칸 진단과 그 근거.

    배포 가능한 산출물이 없는 지역은 `REPORT_NOT_READY`를 반환한다.
    """
    return RegionReport.model_validate(report_service.build_region_report(region_id))
