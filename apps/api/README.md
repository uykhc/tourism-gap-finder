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

운영 DB 스키마는 Alembic으로 관리합니다. Docker 이미지는 애플리케이션 시작 전에
자동으로 아래 명령을 실행합니다.

```bash
alembic upgrade head
```

운영 요청 경로는 분석 패키지나 외부 API를 호출하지 않고, 검증 후 활성화된
사전 계산 산출물만 읽습니다. 알려진 지역의 산출물이 없거나 미완성이면
`REPORT_NOT_READY` 오류를 반환합니다.

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
AUTH_JWT_SECRET=32자 이상의 무작위 비밀값
API_CORS_ORIGINS=https://YOUR-VERCEL-DOMAIN.vercel.app
ANALYSIS_ARTIFACT_ROOT=/data/artifacts
```

이미지에는 API와 분석 패키지 소스, 그리고 `apps/api/app/data`의 지역 표·코드
매핑·경주시 샘플 산출물이 들어갑니다. 분석 작업은 배포 전에 따로 실행하고,
운영에서는 `ANALYSIS_ARTIFACT_ROOT`가 가리키는 영구 볼륨의 활성 release만 읽습니다.

API 키와 데이터베이스 URL은 Railway Variables에만 넣고 Git이나 Vercel의 공개
환경변수에 넣지 않습니다. 외부 관광 API와 OpenAI 키는 사전 계산 작업에서만
사용하며 운영 HTTP 요청에서는 사용하지 않습니다.

## 현재 상태

| 엔드포인트 | 응답 출처 | 필요한 키 |
|---|---|---|
| `/auth/*`, `/users/*` | 데이터베이스 | 없음 |
| `/regions`, `/provinces` | `app/data/regions.csv` 전국 230개 | 없음 |
| `/regions/{id}`, `/regions/{id}/structure` | `app/data/region_features.csv` 전국 230개 | 없음 |
| `/regions/{id}/peers` | `peer_candidates` 산출물 | 없음 |
| `/regions/{id}/gaps` | `relative_supply` + `datalab_navigation` 산출물 | 없음 |
| `/regions/{id}/report` | 위 산출물 + `ai_reports` | 없음 |
| `/regions/{id}/portfolio` | 사전 계산 `portfolios` 산출물 | 없음 |
| `/regions/{id}/hubs` | 사전 계산 `hubs` 산출물 | 없음 |
| `/regions/{id}/performance` | 사전 계산 `performance` 산출물 | 없음 |
| `/compare` | 사전 계산 `portfolios`·`performance`·Peer 산출물 | 없음 |

산출물 엔드포인트는 `app/data/artifacts/`를 기본 루트로 씁니다. 경주시
(`47130`) 샘플 한 벌이 커밋돼 있어 별도 준비 없이 200을 확인할 수 있고, 실제
분석 결과는 `ANALYSIS_ARTIFACT_ROOT`로 다른 경로를 가리켜 씁니다. 샘플은
`scripts/build_sample_artifacts.py`가 실제 생산자 함수를 호출해 만듭니다.

`/report`·`/performance`·`/compare`는 Bearer 인증이 필요합니다. 알려진 지역이지만
배포 가능한 산출물이 없으면 409와 `detail.code: REPORT_NOT_READY`를 반환하고,
존재하지 않는 `region_id`만 404를 반환합니다.

## 전국 release

원천 CSV와 지역별 산출물을 release 디렉터리에 준비한 뒤 다음 명령으로 230개
지역을 검증합니다. 모든 지역이 통과한 경우에만 `current` 링크가 원자적으로
교체됩니다.

```bash
python scripts/build_api_release.py \
  --release-id 2026-09 \
  --artifact-root /data/artifacts \
  --raw-root /data/raw/datalab_navigation \
  --pipeline-config /data/config/release-pipeline.json \
  --activate
```

데이터랩 CSV는 `<raw-root>/<region_id>/navigation.csv`에 두며 `기준연월`,
`목적지 유형`, `목적지 검색량` 열이 필요합니다. release는 `peer_candidates`,
`relative_supply`, `datalab_navigation`, `ai_reports`, `performance`, `portfolios`, `hubs`
각 디렉터리에 `<region_id>.json`을 가져야 합니다. 실패 내역은
`release-manifest.json`에 지역별로 기록됩니다.

`--pipeline-config`는 지역별 생산 명령을 실행하는 선택형 JSON입니다. 각 단계는
`name`, 쉘을 사용하지 않는 `command` 문자열 배열, `outputs` 배열을 가지며
`{region_id}`, `{region_name}`, `{raw_csv}`, `{release_root}`, `{cache_root}`를 사용할 수
있습니다. 완료 단계는 입력 CSV 해시·명령·`ANALYSIS_CODE_VERSION`이 같을 때만
재사용됩니다. 표준 출력과 오류는 지역별 `logs/`, 상태는 `checkpoints/`에 남으므로
중단 후 같은 명령을 다시 실행하거나 `--retry-failed`로 실패 지역만 재시도할 수
있습니다. 외부 API 생산기는 `{cache_root}` 또는 `HANKKEUT_CACHE_ROOT`를 캐시 위치로
사용하도록 구성합니다.

직전 release로 복구할 때는 그 release ID와 `--retry-failed --activate`를 사용합니다.
이미 완료된 230개 지역을 다시 생산하지 않고 검증된 기존 release의 `current` 링크를
원자적으로 복원합니다.

지역 상세·구조 특성은 분석 시점의 전국 구조 변수 스냅숏을 읽습니다. 성과,
비교, 포트폴리오, 중심 관광지 역시 release의 사전 계산 JSON을 반환합니다.

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
