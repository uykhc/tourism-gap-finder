# 분석 파이프라인

수집·정제·분석 CLI를 하나의 배치로 연결할 때 사용할 디렉터리입니다.
현재 이 디렉터리에는 실행 스크립트가 없으며, 각 분석 패키지의 CLI를 직접 실행합니다.

1. 외부 API 응답을 `data/raw/`에 수집한다.
2. 정제·결합 데이터를 `data/interim/`, 분석 입력을 `data/analysis/`에 만든다.
3. 유사 지역, 성과, 관광 공백을 산출해 `results/` 또는 운영 데이터 저장소로 내보낸다.

CLI 명령은 `data/analysis/calculation`, `data/analysis/similarity`,
`data/analysis/evaluation`의 각 도메인 패키지에 있습니다.
