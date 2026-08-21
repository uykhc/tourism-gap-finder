# 모노레포 구조

- `apps/web`: 사용자 화면
- `apps/api`: 화면에 분석 결과를 제공하는 백엔드
- `packages/tourism_data`: 외부 관광·공공 데이터 API 호출
- `packages/analysis`: 유사 지역, 성과 평가, 관광 공백 분석 로직
- `packages/contracts`: 팀 공용 인터페이스와 지역 식별 기준
- `pipelines`: 수집·정제·분석 배치 실행
- `data`: 원본·중간·분석 입력 데이터
- `results`: 재생성 가능한 실행 산출물

인증키는 `.env`에만 두고 Git에 커밋하지 않는다. 브라우저에는 인증키를 절대 노출하지 않는다.
