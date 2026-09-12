"""인증."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..services import regions as region_table
from ..deps import BearerToken, CurrentUser, DbSession
from ..models import RevokedToken, User
from ..schemas import LoginRequest, SignUpRequest, TokenResponse, UserResponse
from ..security import (
    access_token_minutes,
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..serializers import user_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
def signup(payload: SignUpRequest, db: DbSession) -> UserResponse:
    email = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email is already registered")
    if payload.default_region and region_table.find_region(payload.default_region) is None:
        raise HTTPException(
            status_code=422, detail=f"Unknown region_id: {payload.default_region}"
        )
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        default_region=payload.default_region,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_response(user)


@router.post("/login", response_model=TokenResponse, summary="로그인")
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(
        access_token=create_access_token(user.id, remember_me=payload.remember_me),
        expires_in=access_token_minutes(payload.remember_me) * 60,
    )


@router.get("/me", response_model=UserResponse, summary="내 정보")
def me(user: CurrentUser) -> UserResponse:
    return user_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="로그아웃")
def logout(credentials: BearerToken, db: DbSession) -> None:
    claims = decode_token(credentials.credentials)
    jti, expires_at = claims.get("jti"), claims.get("exp")
    if not isinstance(jti, str) or not isinstance(expires_at, (int, float)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not db.scalar(select(RevokedToken).where(RevokedToken.jti == jti)):
        db.add(
            RevokedToken(
                jti=jti, expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc)
            )
        )
        db.commit()
