from __future__ import annotations
import os
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash
PASSWORD_HASH = PasswordHash.recommended()
JWT_SECRET = os.getenv("AUTH_JWT_SECRET", "development-only-change-me")
def hash_password(password: str) -> str: return PASSWORD_HASH.hash(password)
def verify_password(password: str, password_hash: str) -> bool: return PASSWORD_HASH.verify(password, password_hash)
def access_token_minutes(remember_me: bool = False) -> int:
    if remember_me:
        return int(os.getenv("AUTH_REMEMBER_ME_MINUTES", "43200"))
    return int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "60"))
def create_access_token(user_id: int, *, remember_me: bool = False) -> str:
    return jwt.encode({"sub": str(user_id), "jti": str(uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=access_token_minutes(remember_me))}, JWT_SECRET, algorithm="HS256")
def decode_token(token: str) -> dict:
    try: return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
def decode_access_token(token: str) -> int:
    try: return int(decode_token(token)["sub"])
    except (KeyError, TypeError, ValueError) as exc: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
