"""AI 관광 빈칸 리포트."""

from __future__ import annotations

from fastapi import APIRouter

from .. import examples
from ..deps import RegionIdPath
from ..schemas.reports import TourismGapReport

router = APIRouter(prefix="/regions", tags=["reports"])


@router.get(
    "/{region_id}/report",
    response_model=TourismGapReport,
    summary="관광 빈칸 해석 리포트",
)
def get_report(region_id: RegionIdPath) -> TourismGapReport:
    """정량 근거와 출처가 붙은 빈칸 해석."""
    # TODO(실연결): ai_reports.openai_report.OpenAITourismReportGenerator.
    #   생성 결과는 ai_reports.report_schema.validate_report_payload() 를 통과해야 한다.
    del region_id
    return TourismGapReport.model_validate(examples.TOURISM_GAP_REPORT)
