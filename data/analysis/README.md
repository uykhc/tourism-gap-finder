# 분석 모듈

`data/analysis` 아래의 코드는 역할별로 독립 패키지로 나뉩니다.

- `calculation/`: 관광 콘텐츠 수집, 카테고리별 개수·비율·면적당 개수 분석
- `similarity/`: 지역 구조 특성 기반 유사 지역 탐색
- `evaluation/`: 방문자 수·관광수요 및 콘텐츠 포트폴리오 기반 우수 지역 평가
- `contracts/`: 향후 도메인 간에 공유할 타입·Protocol·지역 마스터 계약

개발 환경에서는 세 패키지를 함께 설치합니다.

```bash
python -m pip install -e data/analysis/calculation -e data/analysis/similarity -e data/analysis/evaluation
```

테스트는 각 패키지의 `tests/` 디렉터리에서 실행합니다.
