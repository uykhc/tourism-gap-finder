# 모노레포 구조

- `apps/web`: 사용자 화면
- `apps/api`: 화면에 분석 결과를 제공하는 백엔드
- `data/analysis/calculation`: 외부 관광·공공 데이터 호출, 콘텐츠 집계·관광 공백 분석
- `data/analysis/similarity`: 유사 지역 판별 로직
- `data/analysis/evaluation`: 우수 지역 및 성과 평가 로직
- `data/analysis/contracts`: 팀 공용 인터페이스와 지역 식별 기준
- `pipelines`: 수집·정제·분석 배치 실행
- `data`: 원본·중간·분석 입력 데이터
- `results`: 재생성 가능한 실행 산출물

인증키는 `.env`에만 두고 Git에 커밋하지 않는다. 브라우저에는 인증키를 절대 노출하지 않는다.
