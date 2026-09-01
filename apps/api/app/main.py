from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import RevokedToken, User
from .schemas import LoginRequest, SignUpRequest, TokenResponse, UserResponse
from .security import create_access_token, decode_token, hash_password, verify_password
@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine); yield
app = FastAPI(title="Tourism Gap Finder API", version="0.1.0", lifespan=lifespan)
DbSession = Annotated[Session, Depends(get_db)]
bearer_scheme = HTTPBearer()
@app.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignUpRequest, db: DbSession) -> User:
    email = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(status_code=409, detail="Email is already registered")
    user = User(email=email, password_hash=hash_password(payload.password), default_region=payload.default_region.strip() if payload.default_region else None)
    db.add(user); db.commit(); db.refresh(user); return user
@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(payload.password, user.password_hash): raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(user.id))
@app.get("/auth/me", response_model=UserResponse)
def me(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)], db: DbSession) -> User:
    claims = decode_token(credentials.credentials)
    if db.scalar(select(RevokedToken).where(RevokedToken.jti == claims.get("jti"))):
        raise HTTPException(status_code=401, detail="Token has been logged out")
    try: user = db.get(User, int(claims["sub"]))
    except (KeyError, TypeError, ValueError): raise HTTPException(status_code=401, detail="Invalid or expired token")
    if user is None: raise HTTPException(status_code=401, detail="User not found")
    return user
@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)], db: DbSession) -> None:
    claims = decode_token(credentials.credentials)
    jti, expires_at = claims.get("jti"), claims.get("exp")
    if not isinstance(jti, str) or not isinstance(expires_at, (int, float)):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not db.scalar(select(RevokedToken).where(RevokedToken.jti == jti)):
        from datetime import datetime, timezone
        db.add(RevokedToken(jti=jti, expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc)))
        db.commit()
@app.get("/health")
def health() -> dict[str, str]: return {"status": "ok"}
