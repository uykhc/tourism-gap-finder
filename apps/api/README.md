# API 애플리케이션

프론트엔드가 호출할 HTTP API를 둡니다. 외부 관광 API 키는 이 애플리케이션과
`pipelines/`에서만 읽고, 브라우저로 전달하지 않습니다.

## 실행

```bash
python3 -m pip install -e '.[api]'      # 레포 루트에서
uvicorn apps.api.app.main:app --reload --port 8000
```

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- OpenAPI 스펙: <http://localhost:8000/openapi.json>

프론트는 다른 오리진(Vite dev server)에서 호출하므로 CORS가 켜져 있습니다.
허용 오리진은 `API_CORS_ORIGINS`로 바꿉니다(기본 `http://localhost:5173`).

## Railway 배포

레포 루트의 `Dockerfile`과 `railway.json`은 이 FastAPI 서비스만 빌드한다.
Railway가 제공하는 `PORT`를 사용하며 `/health`를 배포 헬스체크로 사용한다.

배포 전 Railway 서비스 Variables에 최소한 아래 값을 설정한다.

```dotenv
AUTH_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
```

현재 분석 JSON은 이미지에 포함하지 않는다. R2/S3 연동 전에는 해당 결과를
요청할 때 404가 반환된다. API 키와 데이터베이스 URL은 Railway Variables에만
넣고 Git이나 Vercel의 공개 환경변수에 넣지 않는다.

## 현재 상태

`/regions/{id}/peers`, `/regions/{id}/gaps`, `/regions/{id}/report`는 생성된
`data/analysis` JSON 산출물을 읽어 실제 응답 스키마로 변환합니다. 해당 지역의
산출물이 없으면 `404`를 반환합니다. 나머지 분석 엔드포인트는 아직 예시 데이터를
반환합니다.

기본 산출물 루트는 레포의 `data/analysis`이며, 배포 환경에서는
`ANALYSIS_ARTIFACT_ROOT`로 별도 볼륨/경로를 지정할 수 있습니다.

예시 payload는 `app/examples.py`에 모여 있고, 실제 연결 지점은 각 라우터의
`TODO(실연결)` 주석에 적혀 있습니다.

| 엔드포인트 | 연결 대상 | 필요한 키 |
|---|---|---|
| `/regions`, `/regions/{id}` | `hankkeut_contracts.load_regions()` | 없음 |
| `/regions/{id}/structure`, `/peers` | `tourgap.pipeline` + `tourgap.peers` | SGIS |
| `/regions/{id}/portfolio` | `gap_analyzer.analysis.analyze_portfolio` | TourAPI |
| `/regions/{id}/hubs` | `gap_analyzer.hub_api` | HUB |
| `/regions/{id}/performance` | `performance_evaluator.visitor_portfolio_benchmark` | VISITOR |
| `/regions/{id}/gaps` | `datalab_navigation` (상대공급 + 공급압력) | Kakao |
| `/regions/{id}/report` | `ai_reports.openai_report` | OpenAI |

## 구조

```
app/
├── main.py       앱 조립 — OpenAPI 메타, CORS, 라우터 등록
├── deps.py       DbSession, 인증 의존성, region_id 경로 파라미터
├── database.py   SQLAlchemy 엔진·세션
├── models.py     User, RevokedToken
├── security.py   비밀번호 해시, JWT 발급·검증
├── examples.py   스텁이 반환하는 고정 예시 (실연결 시 삭제)
├── schemas/      Pydantic 응답 모델
└── routers/      도메인별 엔드포인트
```

## 규칙

- 조인 키는 **법정동 시군구 코드 5자리**(`region_id`)입니다. 지역명으로 조인하지
  않습니다 — 중구가 5곳, 서구·남구·북구가 4곳이라 값이 섞입니다.
- 결측을 0으로 채우지 않습니다. `null`로 두고 화면에서 '자료 없음'으로 표시합니다.
  0은 '공급 없음'/'성과 바닥'이 되어 순위를 왜곡합니다.
- `app/schemas/reports.py`는 `config/ai/tourism_gap_report.schema.json`의 미러입니다.
  한쪽만 고치면 리포트 생성기의 출력이 API 경계에서 거부됩니다.
