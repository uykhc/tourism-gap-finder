"""지역 마스터와 구조 특성.

지역 단위는 법정동 시군구 코드 5자리 전국 230개다. 지역명은 중구가 5곳,
서구·남구·북구가 4곳이라 조인 키로 쓸 수 없다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import examples
from ..deps import RegionIdPath
from ..schemas.common import Page
from ..schemas.regions import RegionDetail, RegionSummary, StructureProfile
from ..services import regions as region_table

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("", response_model=Page[RegionSummary], summary="지역 목록")
def list_regions(
    q: str | None = Query(default=None, description="시군구명 부분 일치", examples=["경주"]),
    province: str | None = Query(default=None, description="시도명 완전 일치", examples=["경상북도"]),
    limit: int = Query(default=50, ge=1, le=230),
    offset: int = Query(default=0, ge=0),
) -> Page[RegionSummary]:
    """전국 시군구 목록."""
    items = region_table.search_regions(q=q, province=province)
    return Page[RegionSummary].model_validate(
        {"items": items[offset : offset + limit], "total": len(items)}
    )


@router.get("/{region_id}", response_model=RegionDetail, summary="지역 상세")
def get_region(region_id: RegionIdPath) -> RegionDetail:
    """지역 기본 정보."""
    # TODO(실연결): SGIS 인구·면적을 병합한다. 지역 정보 자체는 전국 표에서 온다.
    region = region_table.find_region(region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Unknown region_id: {region_id}")
    return RegionDetail.model_validate({**examples.REGION_DETAIL, **region})


@router.get(
    "/{region_id}/structure",
    response_model=StructureProfile,
    summary="구조 특성 17개 변수",
)
def get_structure(region_id: RegionIdPath) -> StructureProfile:
    """유사도 계산에 쓰는 구조 변수 17개와 출처."""
    # TODO(실연결): hankkeut_similarity.pipeline.load_dataset() 의 features +
    #   provenance. SGIS_CONSUMER_KEY/SECRET 이 없으면 503 (mock 금지).
    del region_id
    return StructureProfile.model_validate(examples.structure_profile())
