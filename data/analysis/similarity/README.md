# 과제 1: 유사 지역 탐색

이 폴더는 관광 데이터 활용 공모전 프로젝트의 과제 1, 즉
`hankkeut_contracts.PeerFinder` 구현만 담당한다.

목표는 사용자가 입력한 `target_region_id`와 구조적 여건이 비슷한
시군구 `peer`를 찾는 것이다. 관광 콘텐츠 수, 방문자 수, 체류시간,
소비액, 숙박시설 수, 음식점 수, 축제 수 같은 관광 성과나 공급 변수는
유사도 계산에 넣지 않는다.

## 구현체

```python
from tourgap import TourgapPeerFinder

finder = TourgapPeerFinder(features)
peers = finder.find_peers("47130", k=15)
```

반환 DataFrame은 공용 계약의 필수 컬럼을 포함한다.

```text
rank, region_id, similarity
```

기본 동작:

- `rank`는 1부터 시작
- target 자신 제외
- `similarity`는 `exp(-distance)`로 계산하며 0~1 범위
- 기본 최대 개수 `15`
- 기본 유사도 하한 `0.40`
- 동일 행정유형 필터 적용
- 마지막에 `validate(frame, PEER_COLUMNS, "peers")` 통과

## 확정 유사도 변수

최종 스키마는 17개다. 같은 현상을 반복 측정하는 변수의 중복 영향은
6개 하위 요인의 총 가중치를 먼저 고정해 제한한다.

| 하위 요인 | 요인 비중 | 변수 | 한국어 설명 | 개별 비중 |
|---|---:|---|---|---:|
| 지역규모 | 10.0% | `area_km2` | 면적 | 5.0% |
| 지역규모 | 10.0% | `total_population` | 총인구 | 5.0% |
| 도시집적 | 10.0% | `population_density` | 인구밀도 | 3.3% |
| 도시집적 | 10.0% | `urbanization_ratio` | 도시화율 | 3.3% |
| 도시집적 | 10.0% | `business_density` | 사업체 밀도 | 3.3% |
| 인구구조 | 10.0% | `average_age` | 평균연령 | 10.0% |
| 자연지리 | 30.0% | `coastal_dummy` | 해안 여부 | 6.0% |
| 자연지리 | 30.0% | `island_ratio` | 도서성 비율 | 6.0% |
| 자연지리 | 30.0% | `forest_ratio` | 산림 비율 | 6.0% |
| 자연지리 | 30.0% | `farmland_ratio` | 농지 비율 | 6.0% |
| 자연지리 | 30.0% | `terrain_relief` | 지형 기복 | 6.0% |
| 기후 | 15.0% | `annual_mean_temperature` | 연평균기온 | 5.0% |
| 기후 | 15.0% | `annual_temperature_range` | 연교차 | 5.0% |
| 기후 | 15.0% | `annual_precipitation` | 연강수량 | 5.0% |
| 산업구조 | 25.0% | `manufacturing_worker_ratio` | 제조업 종사자 비율 | 8.3% |
| 산업구조 | 25.0% | `construction_logistics_worker_ratio` | 건설·물류 종사자 비율 | 8.3% |
| 산업구조 | 25.0% | `knowledge_public_service_worker_ratio` | 지식·공공서비스 종사자 비율 | 8.3% |

합계는 100.0%다. 개별 비중은 각 하위 요인 비중을 요인 안의 변수 수로
나눈 값이다.

로그 변환 대상:

```text
area_km2
total_population
population_density
business_density
annual_precipitation
terrain_relief
```

계산 흐름:

```text
원값 특성
→ 지정 컬럼 log1p 변환
→ z 표준화
→ 그룹/변수 가중치 적용
→ pairwise 가중 Euclidean 거리
→ similarity = exp(-distance)
→ 동일 행정유형 필터
→ 유사도 하한 및 k 적용
```

결측은 0으로 채우지 않는다. 요인 안의 일부 변수가 없으면 해당 요인의
가중치를 사용 가능한 변수끼리 다시 나눈다.

## 현재 데이터 상태

분석 단위는 TourAPI `areaCode2` 마스터의 234개 행을 그대로 쓰지 않는다.
`areaCode2`에는 `청원군`, `마산시`, `진해시`, `남제주군`, `북제주군`처럼
폐지된 지역이 남아 있기 때문이다. 대신 실제 관광자원 응답에 붙은
`lDongRegnCd + lDongSignguCd` 5자리 코드를 기준으로 전국 230개 분석 단위를
만든다. 일반구는 모 시로 합산한다.

지역명은 KTO `area_code/sigungu_code` 마스터를 우선 사용하고, 없을 때만
주소를 보조로 쓴다. KTO 주소 문자열에 섞인 `전남광주통합특별시` 같은
비공식 표기는 분석 지역명으로 사용하지 않는다.

현재 레포와 캐시만으로 실제 유사도에 반영되는 구조 변수는 다음 17개다.

```text
area_km2
total_population
population_density
average_age
urbanization_ratio
coastal_dummy
island_ratio
forest_ratio
farmland_ratio
terrain_relief
annual_mean_temperature
annual_temperature_range
annual_precipitation
business_density
manufacturing_worker_ratio
construction_logistics_worker_ratio
knowledge_public_service_worker_ratio
```

## 산업 구조

SGIS 전국사업체조사 `company.json`의 2024년 자료와 제11차 산업분류를
사용한다. `business_density`는 전체 사업체 수를 SGIS 행정구역 면적으로
나눈 값이다. 세 종사자 비율의 분모에서는 관광 정책 결과와 가까운
I(숙박 및 음식점업), R(예술·스포츠 및 여가 관련 서비스업)을 제외한다.
제조업은 C, 건설·물류는 F·H, 지식·공공서비스는 J·K·M·N·O·P·Q로 집계한다.

## 지형 기복

국토지리정보원 한반도 90m DEM을 SGIS 시군구 경계로 잘라 각 지역의
고도 90백분위수와 10백분위수 차이(`P90 - P10`)를 `terrain_relief`로 쓴다.
일반구는 모 시 경계를 함께 계산하고, 2026년 행정구역 개편 지역은 기존
SGIS 경계의 가중 프록시임을 출처 메타데이터에 표시한다.

```bash
python -m pip install -e '.[geospatial]'
python -m tourgap.terrain
```

산출물은 `data/processed/dem_terrain_relief_by_region.csv`에 저장되며 이후
분석 실행에서 자동으로 병합된다.

## 도시화율

SGIS 도시화지역 경계 `BND_UA_PG.zip`(기준일 2024-06-30)을
`data/raw/urbanization/`에 둔다. DBF의 `SIGUNGU_CD`별 `UA_AREA`를 합산하고
SGIS 행정구역 면적으로 나눠 `urbanization_ratio`를 계산한다. SGIS 일반구는
기존 인구·면적 처리와 동일하게 모 시로 합산한다. GIS 라이브러리 없이 DBF
속성만 읽으며, 원본 SHP와 PRJ는 공간 원자료 검증을 위해 ZIP에 함께 보관한다.
전국 원자료에 시군구 코드가 없는 6개 지역은 도시화지역 폴리곤이 없는
지역이므로 `urban_area_km2=0`으로 처리한다. 일반적인 결측값을 0으로
대체하는 것은 아니다.

## 토지피복

`2025년(2024년 기준) 국가토지피복통계 토지피복지도현황.xlsx`의 시군구
면적 표를 사용한다. 원본은 `data/raw/`에 두고, 아래 명령으로 TourAPI
230개 분석 단위에 맞춘 정적 CSV를 만든다.

```bash
python -m tourgap.land_cover
```

저장 위치:

```text
data/processed/land_cover_by_region.csv
```

`forest_ratio`는 `활엽수림 + 침엽수림 + 혼효림`, `farmland_ratio`는
`경지정리가 된 논 + 경지정리가 안 된 논 + 경지정리가 된 밭 +
경지정리가 안 된 밭 + 시설재배지 + 과수원 + 목장양식장 + 기타재배지`를
각 지역 총면적으로 나눈 값이다.

TourAPI 분석 단위와 원본 통계 단위가 다른 곳은 다음 규칙으로 맞춘다.

- 일반구가 있는 시는 원본 일반구 행을 모 시로 면적 합산
- `세종특별자치시`는 원본 `세종시` 행을 명칭 alias로 사용
- 2026년 인천 분할 지역은 `data/reference/sgis_region_map.csv`의 가중치로
  기존 `중구`, `동구`, `서구` 면적을 배분하고 `proxy`로 표시

## 기후평년값 수집

기후 변수는 기상청 OpenAPI 일자료를 재계산하지 않고, 기상청이 공식
제공하는 1991~2020 기후평년값 파일셋을 사용한다.

공식 페이지:

```text
https://data.kma.go.kr/climate/average30Years/selectAverage30YearsKoreaFileset.do?pgmNo=716
```

`KmaClimateNormalsSource`는 이 파일셋 페이지에서 1991~2020 행 또는 공식
JavaScript의 파일명 규칙을 확인해 원본 파일을 `data/raw/kma/`에 저장한다.
기상청 파일명은 `average30yearsKorea_1991_<type>.xlsx` 형식이지만,
해당 파일셋은 페이지상 1991~2020 기후평년값이다.

사이트 구조가 바뀌거나 다운로드 endpoint가 세션을 요구하면 자동으로 추측하지
않고 예외를 던진다. 그 경우 공식 페이지에서 직접 파일을 받은 뒤
`--monthly`, `--annual` 인자로 넣는다.

```bash
python -m tourgap.climate \
  --monthly data/raw/kma/kma_climate_normals_1991_2020_monthly.xlsx \
  --annual data/raw/kma/kma_climate_normals_1991_2020_annual.xlsx
```

시군구별 정적 기후 feature 생성:

```bash
python -m tourgap.climate
```

저장 위치:

```text
data/processed/kma_climate_normals_by_region.csv
```

이 CSV는 230개 시군구별로 아래 컬럼을 저장한다.

```text
annual_mean_temperature
annual_temperature_range
annual_precipitation
climate_station_ids
climate_station_names
climate_station_distances_km
climate_station_weights
climate_interpolation_method
```

현재 보간 방식은 시군구 중심점 기준 가까운 관측소 3개 역거리 제곱 가중평균이다.
시군구 중심점은 TourAPI 자원 좌표 중앙값으로 만든 proxy이므로, 기후 feature의
`*_source_type`도 `proxy`로 기록한다.

## API 키와 mock 정책

기본 실행은 구조 변수 mock을 허용하지 않는다. `SGIS_CONSUMER_KEY`와
`SGIS_CONSUMER_SECRET`이 없으면 peer 계산을 위한 데이터셋 로딩이
명확한 오류로 멈춘다.

SGIS OpenAPI endpoint는 최신 개발지원센터 `newOpenApi` 문서 기준
`https://sgisapi.mods.go.kr/OpenAPI3`를 기본값으로 쓴다. 구 문서와 일부
예제에는 `https://sgisapi.kostat.go.kr/OpenAPI3`가 남아 있으므로, 운영
환경에서 구 endpoint를 강제해야 하면 `.env`에 아래처럼 지정한다.

```bash
SGIS_API_BASE_URL=https://sgisapi.kostat.go.kr/OpenAPI3
```

개발 중 UI나 파이프라인 연결만 확인해야 할 때만 아래 옵션 중 하나로
합성 구조 변수를 명시적으로 허용한다.

```bash
TOURGAP_ALLOW_MOCK_STRUCTURAL=1 python -m tourgap.main --region 경주시
python -m tourgap.main --region 경주시 --allow-mock-structural
```

mock 결과는 정책 판단이나 검증 보고에 쓰면 안 된다.

## 실행

이 폴더에서 실행:

```bash
python -m pip install -e ../../../contracts
python -m pip install -e .
cp .env.example .env
python -m unittest discover -s tests
python -m tourgap.main --region 경주시
```

루트에서 패키지 설치 없이 실행:

```bash
PYTHONPATH=data/analysis/similarity/src:contracts \
  python -m unittest discover -s data/analysis/similarity/tests

PYTHONPATH=data/analysis/similarity/src:contracts \
  python -m tourgap.main --region 경주시
```

## 산출물

- 구현체: `src/tourgap/peers.py`
- feature 계약/검증: `src/tourgap/feature_builder.py`
- 설정: `src/tourgap/config.py`
- 원자료 로딩 어댑터: `src/tourgap/data_sources.py`
- 검증 문서: `docs/peer-validation.md`
- 테스트: `tests/`

이 폴더는 benchmark 선정, 관광 성과 평가, 콘텐츠 공급 공백 계산을
구현하지 않는다. 해당 작업은 `contracts`의 `PerformanceEvaluator`,
`GapAnalyzer` 계약을 따르는 별도 분석 폴더에서 수행한다.

`data/raw/`, `results/`, `.env`, `__pycache__/`는 `.gitignore` 대상이다.
