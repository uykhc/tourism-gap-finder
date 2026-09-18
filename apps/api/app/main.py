"""Tourism Gap Finder API.

앱 조립만 한다. 엔드포인트는 `routers/`에, 응답 스키마는 `schemas/`에 있다.

분석 산출물(JSON)은 활성화된 release에서 읽어 API 응답 계약으로 변환한다.
운영 요청 중에는 분석이나 외부 API 호출을 실행하지 않는다.
"""

from __future__ import annotations

import os
import json
import logging
import time
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import Base, DATABASE_URL, SessionLocal, engine
from .routers import ALL_ROUTERS
from .security import validate_security_config
from .services import artifacts

logger = logging.getLogger("tourism_gap_finder.api")

TAGS_METADATA = [
    {"name": "auth", "description": "회원가입·로그인·로그아웃"},
    {"name": "users", "description": "회원 정보와 관심 지역"},
    {"name": "regions", "description": "시군구 마스터와 구조 특성 17개 변수"},
    {"name": "peers", "description": "구조적 유사 지역 탐색"},
    {"name": "analysis", "description": "관광자원 공급·중심 관광지·성과·콘텐츠 공백"},
    {"name": "reports", "description": "관광 빈칸 해석 리포트"},
    {"name": "compare", "description": "여러 지역 비교"},
    {"name": "system", "description": "상태 확인"},
]

DESCRIPTION = """
구조적으로 유사한 지역과 비교해 관광 콘텐츠 공백을 진단합니다.

조인 키는 법정동 시군구 코드 5자리(`region_id`)입니다.

Peer·공백·종합 리포트는 사전 생성된 분석 산출물을 반환합니다. 배포 가능한
리포트가 없는 지역은 `REPORT_NOT_READY` 오류를 반환합니다.
""".strip()


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_config()
    environment = os.getenv("API_ENV", "development").strip().lower()
    if environment == "production":
        if DATABASE_URL.startswith("sqlite"):
            raise RuntimeError("production에서는 PostgreSQL AUTH_DATABASE_URL이 필요합니다.")
        origins = _cors_origins()
        if not origins or any(
            not origin.startswith("https://")
            or "localhost" in origin
            or "127.0.0.1" in origin
            for origin in origins
        ):
            raise RuntimeError("production API_CORS_ORIGINS에는 운영 HTTPS 오리진만 허용됩니다.")
        if not os.getenv("ANALYSIS_ARTIFACT_ROOT", "").strip():
            raise RuntimeError("production에서는 ANALYSIS_ARTIFACT_ROOT가 필요합니다.")
    else:
        Base.metadata.create_all(bind=engine)
    yield


def _cors_origins() -> list[str]:
    """프론트는 별도 오리진(Vite dev server)에서 호출한다."""
    raw = os.getenv("API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="Tourism Gap Finder API",
    version="0.1.0",
    description=DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in ALL_ROUTERS:
    app.include_router(router)


@app.exception_handler(HTTPException)
async def structured_http_exception(request: Request, exc: HTTPException):
    detail = exc.detail
    request.state.error_code = (
        detail.get("code")
        if isinstance(detail, dict) and isinstance(detail.get("code"), str)
        else f"HTTP_{exc.status_code}"
    )
    return await http_exception_handler(request, exc)


@app.middleware("http")
async def request_log(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(json.dumps({
            "event": "request_failed",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        }))
        raise
    response.headers["x-request-id"] = request_id
    logger.info(json.dumps({
        "event": "request_complete",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "region_id": request.path_params.get("region_id"),
        "status_code": response.status_code,
        "error_code": getattr(request.state, "error_code", None),
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }, ensure_ascii=False))
    return response


@app.get("/health", tags=["system"], summary="상태 확인")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["system"], summary="운영 의존성 준비 상태")
def ready() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(503, detail={"code": "DATABASE_NOT_READY"}) from exc
    manifest = artifacts.release_manifest()
    if os.getenv("API_ENV", "development").strip().lower() == "production" and (
        manifest is None
        or manifest.get("status") != "complete"
        or manifest.get("complete_count") != 230
        or manifest.get("failed_count") != 0
    ):
        raise HTTPException(503, detail={"code": "ARTIFACT_RELEASE_NOT_READY"})
    return {
        "status": "ready",
        "release_id": str((manifest or {}).get("release_id") or "legacy-development"),
    }
