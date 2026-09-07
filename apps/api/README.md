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

## 현재 상태

`auth`와 `users`만 실제로 동작합니다. **나머지 엔드포인트는 실제 산출물과
같은 형태의 고정 예시 데이터를 반환합니다.** 분석 로직을 붙이기 전에
프론트가 화면을 만들 수 있도록 둔 자리입니다.

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
