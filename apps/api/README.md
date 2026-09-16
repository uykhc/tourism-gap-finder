# API 애플리케이션

프론트엔드가 호출할 HTTP API를 둡니다. 외부 관광 API 키는 분석 작업과
백엔드에서만 읽고, 브라우저로 전달하지 않습니다.

## 실행

```bash
# 레포 루트에서. evaluation이 hankkeut_calculation을 import하므로 설치 순서를 지킨다.
python3 -m pip install -e '.[api,dev]'
python3 -m pip install -e data/analysis/calculation \
                       -e data/analysis/evaluation \
                       -e data/analysis/similarity

uvicorn apps.api.app.main:app --reload --port 8000 --env-file .env
python3 -m pytest apps/api/tests
```

분석 패키지가 없어도 앱은 뜬다. 지역 표와 산출물만 쓰는 엔드포인트는 그대로
동작하고, 패키지나 키가 필요한 엔드포인트만 무엇이 없는지 담은 `503`을
반환한다 (`app/services/analysis_runtime.py`).

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

이미지에는 API와 분석 패키지 소스, 그리고 `apps/api/app/data`의 지역 표·코드
매핑·경주시 샘플 산출물이 들어간다. 분석 작업 자체는 따로 돌리며, 그 결과를
쓰려면 `ANALYSIS_ARTIFACT_ROOT`로 볼륨을 가리킨다. 산출물이 없는 지역은 404가
아니라 `INSUFFICIENT_DATA`로 응답하므로 화면은 그대로 뜬다.

API 키와 데이터베이스 URL은 Railway Variables에만 넣고 Git이나 Vercel의 공개
환경변수에 넣지 않는다. 키가 없는 엔드포인트는 무엇이 없는지 담은 `503`을
반환하며, 모의 데이터를 대신 내보내지 않는다.

## 현재 상태

| 엔드포인트 | 응답 출처 | 필요한 키 |
|---|---|---|
| `/auth/*`, `/users/*` | 데이터베이스 | 없음 |
| `/regions`, `/provinces` | `app/data/regions.csv` 전국 230개 | 없음 |
| `/regions/{id}`, `/regions/{id}/structure` | `app/data/region_features.csv` 전국 230개 | 없음 |
| `/regions/{id}/peers` | `peer_candidates` 산출물 | 없음 |
| `/regions/{id}/gaps` | `relative_supply` + `datalab_navigation` 산출물 | 없음 |
| `/regions/{id}/report` | 위 산출물 + `ai_reports` | 없음 |
| `/regions/{id}/portfolio` | 실시간 TourAPI 관광자원 조회 | TourAPI |
| `/regions/{id}/hubs` | 실시간 중심 관광지 조회 | HUB |
| `/regions/{id}/performance` | **예시 데이터** | VISITOR |
| `/compare` | **예시 데이터** | TourAPI + VISITOR |

산출물을 읽는 세 엔드포인트는 `app/data/artifacts/`를 기본 루트로 씁니다. 경주시
(`47130`) 샘플 한 벌이 커밋돼 있어 별도 준비 없이 200을 확인할 수 있고, 실제
분석 결과는 `ANALYSIS_ARTIFACT_ROOT`로 다른 경로를 가리켜 씁니다. 샘플은
`scripts/build_sample_artifacts.py`가 실제 생산자 함수를 호출해 만듭니다.

`/peers`·`/gaps`는 해당 지역 산출물이 없으면 404입니다. `/report`는 404가 아니라
200과 `summary.diagnosis_status: INSUFFICIENT_DATA`로 응답합니다 — 데이터 부족과
잘못된 요청은 화면에서 구분해야 하기 때문입니다. 존재하지 않는 `region_id`만
404입니다.

아직 예시 데이터를 쓰는 성과·비교 엔드포인트의 payload는 `app/examples.py`에
모여 있습니다. 지역 상세·구조 특성은 분석 시점의 전국 구조 변수 스냅숏을
읽고, 포트폴리오·중심 관광지는 요청 시 외부 API를 호출합니다.

프론트엔드에 건네는 보고서 응답 예시: `tests/fixtures/report_47130.json`.

## 구조

```
app/
├── main.py       앱 조립 — OpenAPI 메타, CORS, 라우터 등록
├── deps.py       DbSession, 인증 의존성, region_id 경로 파라미터
├── database.py   SQLAlchemy 엔진·세션
├── models.py     User, RevokedToken
├── security.py   비밀번호 해시, JWT 발급·검증
├── serializers.py  ORM 응답 변환
├── examples.py   아직 연결되지 않은 엔드포인트의 고정 예시
├── data/         지역 표·코드 매핑·샘플 산출물
├── schemas/      Pydantic 응답 모델
├── services/     지역 표, 산출물 리더, 보고서 조립
└── routers/      도메인별 엔드포인트
```

## 규칙

- 조인 키는 **법정동 시군구 코드 5자리**(`region_id`)입니다. 지역명으로 조인하지
  않습니다 — 중구가 5곳, 서구·남구·북구가 4곳이라 값이 섞입니다.
- 결측을 0으로 채우지 않습니다. `null`로 두고 화면에서 '자료 없음'으로 표시합니다.
  0은 '공급 없음'/'성과 바닥'이 되어 순위를 왜곡합니다.
- 콘텐츠 유형은 영문 코드(`EXPERIENCE_TOURISM` 등)로 오갑니다. 분석 파이프라인과
  `config/ai/tourism_gap_report.schema.json`도 같은 코드를 씁니다. 한국어 라벨은
  프론트엔드가 매핑합니다.
- `app/schemas/reports.py`는 화면 전용 응답이고 `config/ai/tourism_gap_report.schema.json`은
  LLM 출력 계약입니다. 둘은 더 이상 같은 모양이 아닙니다 — 보고서 응답은 LLM
  출력에 산출물 수치를 더해 `app/services/report.py`가 조립합니다. 콘텐츠 유형
  코드만 양쪽에서 같아야 하며, 그건 계약 테스트가 확인합니다.
- 표시용 문자열(`"0.70배"`)을 만들지 않습니다. 반올림하지 않은 숫자를 내리고
  포맷팅은 프론트엔드가 합니다.
