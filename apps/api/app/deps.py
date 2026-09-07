"""라우터가 공유하는 의존성과 경로 파라미터."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import get_db
from .models import RevokedToken, User
from .security import decode_token

DbSession = Annotated[Session, Depends(get_db)]

bearer_scheme = HTTPBearer()
BearerToken = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]

#: 법정동 시군구 코드 5자리. 지역명으로 조인하면 중구가 5곳이라 값이 섞인다.
RegionIdPath = Annotated[
    str,
    Path(
        pattern=r"^\d{5}$",
        examples=["47130"],
        description="법정동 시군구 코드 5자리 (경주시 47130)",
    ),
]


def current_user(credentials: BearerToken, db: DbSession) -> User:
    """폐기되지 않은 토큰이 가리키는 사용자."""
    claims = decode_token(credentials.credentials)
    if db.scalar(select(RevokedToken).where(RevokedToken.jti == claims.get("jti"))):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been logged out"
        )
    try:
        user = db.get(User, int(claims["sub"]))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]
