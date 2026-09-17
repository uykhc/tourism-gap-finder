# 전국 우수 관광 지역 선별

`hankkeut-visitor-portfolio`는 전국 포트폴리오 벤치마크 결과를 입력받아
방문자 수와 관광 수요 지수로 우수 지역을 선정한다.

```bash
PYTHONPATH=data/analysis/calculation/src:data/analysis/evaluation/src \
hankkeut-visitor-portfolio \
  --input results/portfolio_benchmarks/national_portfolio_benchmark_YYYYMMDD.json \
  --config config/national/performance_evaluator.json
```

## 전국 식별 규칙

결과의 내부 지역 키는 `<area_code>:<sigungu_code>`다. `region_name`은 화면
표시용으로만 사용하며, 전국에서 같은 이름의 시군구를 하나로 합산하지 않는다.

방문자 수 API가 시도명을 포함한 지역명(예: `서울특별시 중구`)을 주면 자동으로
매칭한다. API의 표기가 다른 경우 포트폴리오 지역 설정에 정확한
`visitor_region_name`을 넣는다.

```json
{
  "province_name": "서울특별시",
  "region_name": "중구",
  "area_code": "1",
  "sigungu_code": "110",
  "visitor_region_name": "서울 중구"
}
```

동명 지역에 대해 API가 `중구`처럼 시도 정보 없는 값만 주면 명령은 실패한다.
이는 잘못된 지역을 합산한 전국 순위를 만드는 것을 방지하기 위한 동작이다.
