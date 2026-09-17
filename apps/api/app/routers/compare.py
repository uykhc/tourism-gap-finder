"""지역 비교."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import StringConstraints

from ..deps import CurrentUser
from ..schemas.compare import ComparisonResult
from ..services import artifacts

router = APIRouter(tags=["compare"])

#: 5자리 제약은 항목에 걸어야 한다. 리스트 자체에 pattern을 주면
#: pydantic이 list에 문자열 제약을 적용하려다 실패한다.
RegionId = Annotated[str, StringConstraints(pattern=r"^\d{5}$")]

RegionIds = Annotated[
    list[RegionId],
    Query(
        min_length=2,
        max_length=5,
        description="비교할 법정동 시군구 코드. 첫 번째가 기준 지역이 된다",
        examples=[["47130", "47110", "44210"]],
    ),
]


@router.get("/compare", response_model=ComparisonResult, summary="여러 지역 나란히 비교")
def compare_regions(region_ids: RegionIds, _: CurrentUser) -> ComparisonResult:
    """지역 2~5곳의 공급 구성과 성과 비교표."""
    return ComparisonResult.model_validate(artifacts.comparison(region_ids))
