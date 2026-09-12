"""AI 관광 빈칸 리포트."""

from __future__ import annotations

from fastapi import APIRouter

from ..services import artifacts
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
    return TourismGapReport.model_validate(artifacts.report(region_id))
