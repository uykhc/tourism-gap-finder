# 韓끗 관광 빈칸 분석

한국관광공사 OpenAPI로 경기도의 관광자원 포트폴리오와 대표 관광지 주변
체류 보완 자원을 분석합니다. `docs/`의 결과 문서는 아래 명령으로 생성되는
JSON·CSV를 해석해 정리한 문서입니다.

## 1. 처음 실행하기

Python 3.11 이상이 필요하며 외부 Python 패키지는 사용하지 않습니다.

```bash
git clone <repository-url>
cd hankkeut-analysis
python3 -m pip install -e .
cp .env.example .env
chmod 600 .env
```

`.env`에 발급받은 키를 입력합니다.

```dotenv
# 국문 관광정보 서비스(KorService2)
KOR_TOUR_API_SERVICE_KEY='인증키'

# 기초지자체 중심 관광지 정보(LocgoHubTarService1)
HUB_TOUR_API_SERVICE_KEY='인증키'

# 이동통신 기반 지역별 방문자 수(DataLabService)
VISITOR_API_SERVICE_KEY='인증키'
```

- 포트폴리오 분석은 `KOR_TOUR_API_SERVICE_KEY`만 필요합니다.
- 체류 전환 분석은 두 키가 모두 필요합니다.
- 방문자 수 상위 지역 baseline은 `KOR_TOUR_API_SERVICE_KEY`와
  `VISITOR_API_SERVICE_KEY`가 필요합니다.
- `.env`와 `results/`는 Git에 올라가지 않습니다.
- 인증키는 공공데이터포털의 Encoding·Decoding 키를 모두 사용할 수 있습니다.

설치 확인:

```bash
python3 -m unittest discover -s tests -q
```

## 2. 포트폴리오 빈칸 문서 재현

### 전체 경기도 기준

경기도 28개 시를 대상으로 8개 관광자원 유형의
개수/km²와 중앙값·상위 25% 지점(P75) 등 분포 통계를 계산합니다.

```bash
hankkeut-portfolio-benchmark
```

- 설정·면적: `config/gyeonggi_portfolio_benchmarks.json`
- 생성 결과: `results/portfolio_benchmarks/gyeonggi_portfolio_benchmark_<실행일>_*`

### 이동통신 방문자 수 상위 지역 기준

위 명령이 끝난 다음 실행합니다. 가장 최근 전체 경기도 JSON을 자동으로
읽고, 최신 공통 월의 방문자 수·관광 자원 수요·관광 수요 강도를 40:30:30으로
결합해 우수 관광 지역 상위 5개 시를 선정합니다.

```bash
hankkeut-visitor-portfolio
```

- 선정 설정: `config/gyeonggi_visitor_portfolio_benchmark.json`
- 생성 결과: `results/portfolio_benchmarks/gyeonggi_visitor_portfolio_benchmark_<실행일>_*`

특정 전체 결과를 사용하려면 다음처럼 지정합니다.

```bash
hankkeut-visitor-portfolio \
  --input results/portfolio_benchmarks/gyeonggi_portfolio_benchmark_YYYYMMDD.json
```

## 3. 체류 전환 빈칸 문서 재현

중심 관광지 API의 2025년 3월 순위와 현재 KorService2 등록 자원을 결합해
대표 관광지 반경 1km·2km의 음식점·숙박·문화시설·행사·쇼핑을 계산합니다.

```bash
# 경기도 28개 시 × 중심 관광지 순위 상위 3개
hankkeut-benchmark

# 실제 중분류별 후보 목록
hankkeut-discover \
  --category-middle 자연관광 \
  --category-middle 레저스포츠

```

- 기본 설정: `config/gyeonggi_benchmarks.json`
- 생성 결과: `results/benchmarks/`

명령은 JSON·CSV를 생성하며 `.md`를 자동으로 덮어쓰지는 않습니다. 문서를
갱신할 때는 실패 CSV가 비어 있는지 확인한 뒤 수집일과 표본 수를 새 결과에
맞춰 수정합니다. 임계값과 후보 판정은 새 기준을 정한 뒤 별도로 적용합니다.

API 지역 코드만 먼저 확인하려면 다음 명령을 사용합니다.

```bash
hankkeut-benchmark --validate-only
hankkeut-portfolio-benchmark --validate-only
```

## 4. 결과를 읽는 기준

현재 결과에는 자동 임계값이나 후보 판정이 포함되지 않습니다. `minimum`,
`median`, `p75`, `maximum`, `zero_rate_percentage`를 비교 참고값으로 보고,
새 threshold 정의가 확정되면 그 기준을 별도 로직으로 추가합니다.

분석 결과는 실제 방문객·매출·사업성을 뜻하지 않습니다. 한국관광공사 API에
등록된 관광자원의 **상대적 공급 구조**만 보여줍니다. API 등록 현황은 바뀔 수
있으므로 다시 실행한 수치는 문서에 적힌 2026년 8월 4일 결과와 달라질 수
있습니다.

## 5. 유사 지역 그룹

경기도 MVP와 전국 시군구 확장에 공통으로 사용할 유사 지역 그룹은 구조 특성으로만 만듭니다. 관광 콘텐츠 개수·밀도·유형 비율은 그룹 생성이 아니라 관광 빈칸 진단에 사용합니다.

```bash
hankkeut-similarity-groups --config config/gyeonggi_similarity_groups.json
hankkeut-similarity-groups --config config/national_similarity_groups.json
```

입력 CSV 형식과 필요한 공공 데이터 출처는 [유사 지역 데이터 가이드](docs/similarity-data-sources.md)에 정리했습니다.

## 5. 개별 지역 확인

전체 배치가 아니라 한 지역만 확인할 때 사용합니다.

```bash
hankkeut-portfolio \
  --region-name 수원시 \
  --area-code 31 \
  --sigungu-code 1 \
  --area-km2 121.09

hankkeut-stay \
  --region-name 수원시 \
  --base-ym 202503 \
  --hub-area-code 41 \
  --hub-sigungu-code 41115 \
  --tour-area-code 31 \
  --tour-sigungu-code 1
```

면적은 TourAPI가 제공하지 않으므로 개별 실행 시 직접 입력해야 합니다.
배치 분석의 면적과 지역 코드는 `config/`에 포함되어 있습니다.

## 문서 목록

- `docs/hankkeut-analysis-handoff.md`: 분석 기획과 빈칸 정의
- `config/gyeonggi_portfolio_benchmarks.json`: 경기도 28개 시 포트폴리오 기준(군은 현재 비활성화)
- `config/gyeonggi_visitor_portfolio_benchmark.json`: 방문자 수 상위 지역 기준
- `config/gyeonggi_benchmarks.json`: 대표 관광지 반경 체류 보완 기준

패키지를 설치하지 않으려면 `PYTHONPATH=src python3 -m <모듈명>` 형태로
실행할 수 있지만, 팀 작업에서는 `pip install -e .` 방식을 권장합니다.
