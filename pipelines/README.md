# 분석 파이프라인

수집·정제·분석 CLI를 하나의 배치로 연결할 때 사용할 디렉터리입니다.
`api-release.json`은 API release 생산 명령을 선언합니다. 전국 단위 작업은
`global_stages`, 지역별 작업은 `region_stages`에 둡니다.

1. 외부 API 응답을 `data/raw/`에 수집한다.
2. 정제·결합 데이터를 `data/interim/`, 분석 입력을 `data/analysis/`에 만든다.
3. 유사 지역, 성과, 관광 공백을 산출해 `results/` 또는 운영 데이터 저장소로 내보낸다.

CLI 명령은 `data/analysis/calculation`, `data/analysis/similarity`,
`data/analysis/evaluation`의 각 도메인 패키지에 있습니다.

## 현재 자동 연결 범위

설정에는 SGIS 전국 경계, Peer, Kakao 콘텐츠 DB, Performance, Portfolio, Hub,
데이터랩 공급압력, 상대공급, AI 보고서 생산 단계가 연결돼 있습니다. 외부 입력이
없는 단계는 명령을 호출하지 않고 체크포인트에 `blocked`로 기록합니다. Peer 후보는
전국 구조 변수 파일만 필요하므로 바로 실행할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts\build_api_release.py `
  --release-id local-peers `
  --pipeline-config pipelines\api-release.json `
  --only-stage peer_candidates
```

이 명령은 생성 결과를 `data/releases/releases/local-peers/peer_candidates/`에
저장합니다. 입력 해시와 코드 버전이 같으면 다음 실행에서는 완료 체크포인트를
재사용합니다. 부분 실행은 release를 활성화하지 않습니다.

전체 준비 상태는 외부 호출 없이 확인할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe scripts\build_api_release.py `
  --release-id 2026-09 `
  --pipeline-config pipelines\api-release.json `
  --base-year-month 202608 `
  --preflight
```

출력에는 키의 존재 여부만 표시되고 값은 포함되지 않습니다. `ready`는 데이터랩
CSV와 7종 산출물이 전국 230개 지역에 모두 있을 때만 `true`입니다.
또한 release 안의 전국 WGS84 경계, PostgreSQL 콘텐츠 DB, 기준월, TourAPI 미매핑
지역도 별도로 보고합니다. `AUTH_DATABASE_URL`이 설정돼 있어도 SQLite이면 콘텐츠
DB 준비 완료로 보지 않습니다.

전체 실행에는 다음 입력이 추가로 필요합니다.

- `data/raw/national_sigungu_overrides.geojson`: SGIS가 아직 제공하지 않는 인천
  신설 4개 구의 공식 WGS84 경계와 TourAPI `area_code`·`sigungu_code`
- `CONTENT_DATABASE_URL`: `001_content_collection.sql`을 적용할 PostgreSQL
- `<raw-root>/<region_id>/navigation.csv`: 전국 데이터랩 월별 CSV
- `--base-year-month YYYYMM`: 중심 관광지·방문자·관광 수요지수의 공통 기준월

데이터랩 다운로드 대기 목록과 각 파일의 권장 경로는 다음 명령으로 확인합니다.

```powershell
.\.venv\Scripts\python.exe scripts\datalab_intake_manifest.py
```

파일이 있으면 필수 열, 데이터 행, `YYYYMM` 형식을 검사하며 값이 없다고 0으로
간주하지 않습니다.

`sgis_boundaries` 단계는 SGIS EPSG:5179 경계를 WGS84로 변환하고 일반구를 모 시로
합칩니다. 2026년 인천 신설 4개 구는 SGIS 2025 경계와 TourAPI 코드에 아직 없으므로
공식 override가 없으면 명시적으로 실패합니다. 이전 중구·동구·서구 경계를 복제하거나
면적 비율로 임의 분할하지 않습니다. 완성된 경계는 release의
`source-boundaries/national_sigungu.geojson`에 저장됩니다.

## 지역별 생산자 계약

| 산출물 | 생산 입력 | 준비되지 않았을 때 |
|---|---|---|
| `source-boundaries` | SGIS + 인천 신설 구 공식 override | 누락 지역을 표시하고 단계 실패 |
| `peer_candidates` | `region_features.csv` | 단계 실패 |
| `portfolios` | KorService2 | 키/수집 결과 누락으로 기록 |
| `hubs` | 중심 관광지 API | 키/수집 결과 누락으로 기록 |
| `performance` | 방문자수 API + 관광 수요지수 API | 키/수집 결과 누락으로 기록 |
| `datalab_navigation` | 지역별 `navigation.csv` | `missing-input`, 임의의 0 생성 금지 |
| `relative_supply` | 콘텐츠 DB, Peer, Performance | 성과가 더 높은 Peer나 선행 산출물 누락으로 기록 |
| `ai_reports` | 공급 분석, 상대공급, 성과 검증 Peer | 선행 산출물 또는 OpenAI 키 누락으로 기록 |

생산자는 최종적으로 `<release-root>/<산출물>/<region_id>.json`을 써야 합니다.
mock이나 빈 값을 운영 release의 대체 데이터로 만들지 않습니다.
