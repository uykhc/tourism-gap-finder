"""Tourism Gap Finder API.

앱 조립만 한다. 엔드포인트는 `routers/`에, 응답 스키마는 `schemas/`에 있다.

분석 로직(`packages/analysis`, `data/analysis/similarity`)은 아직 붙지 않았다.
인증과 회원 정보를 뺀 나머지 엔드포인트는 실제 산출물과 같은 형태의 고정
예시를 돌려준다. 연결 지점은 각 라우터의 TODO 주석에 적혀 있다.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import ALL_ROUTERS

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

⚠️ `auth`, `users`를 제외한 모든 엔드포인트는 고정 예시 데이터를 반환합니다.
""".strip()


@asynccontextmanager
async def lifespan(_: FastAPI):
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


@app.get("/health", tags=["system"], summary="상태 확인")
def health() -> dict[str, str]:
    return {"status": "ok"}
