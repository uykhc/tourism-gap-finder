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
    """유사 지역 · 우수 지역 · 상대적 빈칸 · 절대적 빈칸을 묶은 종합 리포트."""
    # TODO(실연결): PeerFinder → PerformanceEvaluator → relative_supply →
    #   navigation_demand 결과를 모아 ai_reports.openai_report 에 넘긴다.
    del region_id
    return TourismGapReport.model_validate(examples.tourism_gap_report())
