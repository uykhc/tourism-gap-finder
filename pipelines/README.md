# 분석 파이프라인

배치 실행 진입점을 둡니다.

1. 외부 API 응답을 `data/raw/`에 수집한다.
2. 정제·결합 데이터를 `data/interim/`, 분석 입력을 `data/analysis/`에 만든다.
3. 유사 지역, 성과, 관광 공백을 산출해 `results/` 또는 운영 데이터 저장소로 내보낸다.

현재 CLI 명령은 `data/analysis/calculation`, `data/analysis/similarity`,
`data/analysis/evaluation`의 각 도메인 패키지에 있으며, 파이프라인 자동화가
필요해질 때 이 디렉터리의 스크립트에서 해당 명령을 순서대로 호출한다.
