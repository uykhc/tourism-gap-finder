from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .common import RegionRef

_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")

PASSWORD_RULE = "영문·숫자 포함 8자 이상"


def validate_password_strength(value: str) -> str:
    if not (
        _HAS_LETTER.search(value)
        and _HAS_DIGIT.search(value)
    ):
        raise ValueError(f"비밀번호는 {PASSWORD_RULE}이어야 합니다.")
    return value


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128, description=PASSWORD_RULE)
    password_confirm: str = Field(min_length=8, max_length=128)
    default_region: str | None = Field(
        default=None,
        pattern=r"^\d{5}$",
        examples=["51210"],
        description="관심 지역 코드. 건너뛰면 null",
    )
    _check_password = field_validator("password")(validate_password_strength)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("password and password_confirm must match")
        return self

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = Field(default=False, description="로그인 상태 유지")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    default_region: RegionRef | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="토큰 유효 시간(초)", examples=[3600])


class UpdateUserRequest(BaseModel):
    """관심 지역 변경."""

    default_region: str | None = Field(
        default=None,
        pattern=r"^\d{5}$",
        examples=["51210"],
        description="법정동 시군구 코드 5자리. null이면 관심 지역 해제",
    )


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128, description=PASSWORD_RULE)
    new_password_confirm: str = Field(min_length=8, max_length=128)

    _check_password = field_validator("new_password")(validate_password_strength)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.new_password_confirm:
            raise ValueError("new_password and new_password_confirm must match")
        return self
