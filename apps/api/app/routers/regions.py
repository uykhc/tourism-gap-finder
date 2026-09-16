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
    region = region_table.find_region(region_id)
    if region is None:
        raise HTTPException(status_code=404, detail=f"Unknown region_id: {region_id}")
    features = region_table.find_region_features(region_id)
    if features is None:  # 지역 표와 구조 변수 표의 정합성 검증에 대한 방어선
        raise HTTPException(status_code=503, detail=f"지역 구조 변수가 없습니다: {region_id}")
    return RegionDetail.model_validate(
        {
            **region,
            "area_km2": features["area_km2"],
            "total_population": int(features["total_population"]),
            "coastal": bool(features["coastal_dummy"]),
        }
    )


@router.get(
    "/{region_id}/structure",
    response_model=StructureProfile,
    summary="구조 특성 17개 변수",
)
def get_structure(region_id: RegionIdPath) -> StructureProfile:
    """유사도 계산에 쓰는 구조 변수 17개와 출처."""
    region = region_table.find_region(region_id)
    features = region_table.find_region_features(region_id)
    if region is None or features is None:
        raise HTTPException(status_code=404, detail=f"Unknown region_id: {region_id}")

    # 기존 예시가 가진 라벨·그룹·가중치·출처 메타데이터는 계약 템플릿으로
    # 재사용하되, 대상과 17개 값은 전국 구조 변수 스냅숏에서 교체한다.
    payload = examples.structure_profile()
    payload["target"] = region
    for item in payload["features"]:
        item["value"] = features[item["feature"]]
    return StructureProfile.model_validate(payload)
