"""지역 마스터 조회.

TODO(실연결): hankkeut_contracts.load_regions() 로 교체한다.
"""

from __future__ import annotations

from typing import Any

from . import examples


def all_regions() -> list[dict[str, Any]]:
    return examples.REGIONS


def find_region(region_id: str) -> dict[str, Any] | None:
    return next(
        (region for region in all_regions() if region["region_id"] == region_id), None
    )


def search_regions(
    *, q: str | None = None, province: str | None = None
) -> list[dict[str, Any]]:
    """시군구명 부분 일치와 시도명 완전 일치로 거른다."""
    items = all_regions()
    if province:
        items = [item for item in items if item["province_name"] == province]
    if q:
        items = [item for item in items if q in item["region_name"]]
    return items


def provinces() -> list[dict[str, Any]]:
    return examples.PROVINCES
