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

설정에는 Peer, Performance, Kakao DB run 검증, Portfolio, Hub, 데이터랩
공급압력, 상대공급, AI 보고서 생산 단계가 연결돼 있습니다. 외부 입력이 없는
단계는 명령을 호출하지 않고 체크포인트에 `blocked`로 기록합니다. 기본 경로는
Kakao 수집기·SGIS 경계에는 직접 연결되지 않으며, 콘텐츠 DB는 읽기만 합니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.build_api_release `
  --release-id local-peers `
  --pipeline-config pipelines\api-release.json `
  --only-stage peer_candidates
```

이 명령은 생성 결과를 `data/releases/releases/local-peers/peer_candidates/`에
저장합니다. 입력 해시와 코드 버전이 같으면 다음 실행에서는 완료 체크포인트를
재사용합니다. 부분 실행은 release를 활성화하지 않습니다.

전체 준비 상태는 외부 호출 없이 확인할 수 있습니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.build_api_release `
  --release-id 2026-09 `
  --pipeline-config pipelines\api-release.json `
  --base-year-month 202608 `
  --preflight
```

출력에는 키의 존재 여부만 표시되고 값은 포함되지 않습니다. `ready`는 전국
Peer·성과·중심 관광지 230개와 제공 가능한 포트폴리오 226개가 검증되면
`true`입니다. DataLab·상대 공급·AI 보고서는 지정 5개 지역의 고급 범위로
별도 보고하며 기본 release 활성화를 막지 않습니다. 출시 검증에서는
`--require-advanced`를 사용해 5/5가 아니면 활성화를 거부합니다.

지정 5개 지역의 고급 분석을 완성하려면 다음 입력이 추가로 필요합니다.

- `CONTENT_DATABASE_URL`: Kakao 담당자가 적재한 PostgreSQL 읽기 연결
- `KAKAO_COLLECTION_RUN_ID`: 출시 대상으로 고정한 completed 수집 run UUID
- `<raw-root>/<region_id>/navigation.csv`: 지정 5개 지역과 선정된 비교 지역의
  `202509~202608` 유형별 검색건수 기간 합계 CSV
- `--base-year-month YYYYMM`: 중심 관광지·방문자·관광 수요지수의 공통 기준월
- `OPENAI_API_KEY`: 마지막 AI 보고서 생성 단계에서만 사용

데이터랩 다운로드 대기 목록과 각 파일의 권장 경로는 다음 명령으로 확인합니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.datalab_intake_manifest
```

파일이 있으면 `카테고리중분류명`·`유형별 검색건수`, 9개 관광 유형,
중복, 음수 여부를 검사합니다. 비율과 이름 없는 순위 열은 무시하고, 전체
검색건수는 공개된 9개 유형 건수의 합으로 산출합니다. 월별 값을 임의로
배분하지 않으며 파일 밖 release 설정에 `202509~202608` 기간을 기록합니다.

`kakao_database` 단계는 대상 5개와 실제 선정 Peer의 합집합을 계산하고 한 DB run에
모두 있는지 검증합니다. 한글·영문 유형은 영문 6개 코드로 정규화하고, 중복·누락,
음수·비정수 건수, 미완성 수집, 잘린 타일은 실패합니다. run ID와 정규화 결과 해시,
수집 메타데이터는 `source-markers/`에 저장됩니다.

## 지역별 생산자 계약

| 산출물 | 생산 입력 | 준비되지 않았을 때 |
|---|---|---|
| `source-markers/kakao-content.json` | Kakao DB의 고정 completed run | 계약 또는 필수 지역 누락으로 단계 실패 |
| `peer_candidates` | `region_features.csv` | 단계 실패 |
| `portfolios` | KorService2 | 키/수집 결과 누락으로 기록 |
| `hubs` | 중심 관광지 API | 키/수집 결과 누락으로 기록 |
| `performance` | 방문자수 API + 관광 수요지수 API | 키/수집 결과 누락으로 기록 |
| `datalab_navigation` | 지역별 `navigation.csv` | `missing-input`, 임의의 0 생성 금지 |
| `relative_supply` | Kakao DB run, Peer, Performance | 성과가 더 높은 Peer나 선행 산출물 누락으로 기록 |
| `ai_reports` | 공급 분석, 상대공급, 성과 검증 Peer | 선행 산출물 또는 OpenAI 키 누락으로 기록 |

생산자는 최종적으로 `<release-root>/<산출물>/<region_id>.json`을 써야 합니다.
mock이나 빈 값을 운영 release의 대체 데이터로 만들지 않습니다.
