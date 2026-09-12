"""시·도 목록."""

from __future__ import annotations

from fastapi import APIRouter

from ..services import regions as region_table
from ..schemas.common import Page
from ..schemas.regions import ProvinceSummary

router = APIRouter(tags=["regions"])


@router.get("/provinces", response_model=Page[ProvinceSummary], summary="시·도 목록")
def list_provinces() -> Page[ProvinceSummary]:
    """지역 선택 1단계에 쓰는 시·도 17개."""
    items = region_table.provinces()
    return Page[ProvinceSummary].model_validate({"items": items, "total": len(items)})
