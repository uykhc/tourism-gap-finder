"""회원 정보."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete

from .. import region_master
from ..deps import CurrentUser, DbSession
from ..models import User
from ..schemas import ChangePasswordRequest, UpdateUserRequest, UserResponse
from ..security import hash_password
from ..serializers import user_response

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserResponse, summary="관심 지역 변경")
def update_me(
    payload: UpdateUserRequest, user: CurrentUser, db: DbSession
) -> UserResponse:
    """null을 보내면 관심 지역을 해제한다."""
    region_id = payload.default_region
    if region_id and region_master.find_region(region_id) is None:
        raise HTTPException(status_code=422, detail=f"Unknown region_id: {region_id}")
    user.default_region = region_id
    db.commit()
    db.refresh(user)
    return user_response(user)


@router.patch(
    "/me/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="비밀번호 변경",
)
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: DbSession
) -> None:
    user.password_hash = hash_password(payload.new_password)
    db.commit()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, summary="회원 탈퇴")
def delete_me(user: CurrentUser, db: DbSession) -> None:
    """계정 정보와 관심 지역을 삭제한다. 복구할 수 없다."""
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
