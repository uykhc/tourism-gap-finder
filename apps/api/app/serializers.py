"""ORM 객체를 응답 스키마로 옮긴다."""

from __future__ import annotations

from .services import regions as region_table
from .models import User
from .schemas.auth import UserResponse
from .schemas.common import RegionRef


def region_ref(region_id: str | None) -> RegionRef | None:
    """관심 지역 코드를 시도명이 붙은 지역 정보로 바꾼다."""
    if not region_id:
        return None
    region = region_table.find_region(region_id)
    return None if region is None else RegionRef.model_validate(region)


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        default_region=region_ref(user.default_region),
        created_at=user.created_at,
    )
