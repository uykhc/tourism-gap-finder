"""지역 관광 보고서."""

from __future__ import annotations

from fastapi import APIRouter

from ..deps import RegionIdPath
from ..schemas.reports import RegionReport
from ..services import report as report_service

router = APIRouter(prefix="/regions", tags=["reports"])


@router.get(
    "/{region_id}/report",
    response_model=RegionReport,
    summary="지역 관광 보고서",
)
def get_report(region_id: RegionIdPath) -> RegionReport:
    """유형별 공급 빈칸 진단과 그 근거.

    분석 산출물이 없는 지역도 404가 아니라 200과
    `summary.diagnosis_status: INSUFFICIENT_DATA`로 응답한다. 존재하지 않는
    `region_id`만 404다.
    """
    return RegionReport.model_validate(report_service.build_region_report(region_id))
