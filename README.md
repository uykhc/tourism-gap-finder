# 韓끗 관광 빈칸 분석

전국 시군구의 구조적 유사 지역을 찾고, 관광 성과가 높은 유사 지역을 기준으로 관광 콘텐츠 공백을 진단하는 모노레포입니다.

## 디렉터리

```text
apps/                 프론트엔드(web)와 백엔드(api)
packages/
  analysis/           데이터 수집·유사 지역·성과·공백 분석 Python 패키지
  contracts/          팀 공용 인터페이스와 지역 마스터
config/               지역별 분석 설정
data/                 reference / raw / interim / analysis 데이터
pipelines/            수집·정제·분석 배치 실행 진입점
results/              실행 산출물(Git 제외)
docs/                 방법론·구조·데이터 출처·결과 문서
```

세부 역할과 팀 공통 규칙은 [COLLABORATION.md](data/analysis/COLLABORATION.md), 전체 구조는 [모노레포 구조 문서](docs/architecture/monorepo-structure.md)를 참고합니다.

## 설치

### 데이터 분석 및 API

Python 3.11 이상이 필요합니다.

```bash
python3 -m pip install -e .
cp .env.example .env
chmod 600 .env
```

`.env`에는 발급받은 공공데이터포털 서비스 키를 입력합니다. 인증키는 API·배치 프로세스에서만 읽으며 프론트엔드 코드에 넣지 않습니다.

```dotenv
KOR_TOUR_API_SERVICE_KEY=
HUB_TOUR_API_SERVICE_KEY=
VISITOR_API_SERVICE_KEY=
```

### 프론트엔드

Node.js 24가 필요합니다.

```bash
cd apps/web
corepack enable
yarn install --immutable
cp .env.example .env.local
yarn dev
```

프론트엔드의 정적 검사와 프로덕션 빌드는 다음 명령으로 확인합니다.

```bash
cd apps/web
yarn check-all
yarn build
```

`main` 브랜치를 대상으로 하는 PR과 `main` push에서는 GitHub Actions가 동일한 검사를
실행합니다. Vercel 프로젝트의 Root Directory는 `apps/web`으로 설정합니다.

## 현재 분석 명령

```bash
# 경기도 시 관광자원 포트폴리오 수집
hankkeut-portfolio-benchmark \\
  --config config/gyeonggi/portfolio_benchmark.json

# 방문자·관광 수요 기반 상위 5개 시 선정
hankkeut-visitor-portfolio \\
  --config config/gyeonggi/performance_evaluator.json

# 구조 특성 기반 유사 지역 그룹
hankkeut-similarity-groups \\
  --config config/gyeonggi/similarity_groups.json
```

데이터랩 월별 내비게이션 검색량은 다음처럼 카카오 공급 장소 수와 결합합니다.

```bash
hankkeut-datalab-navigation \\
  --input data/raw/datalab_navigation/suwon/202501-202607/navigation_destination_type_search_count_monthly.csv \\
  --region-name 수원시 \\
  --kakao-collection data/analysis/kakao_regions/kakao_tourism_content.json \\
  --import-output data/analysis/datalab_navigation/suwon_navigation_demand_import.json \\
  --output data/analysis/datalab_navigation/suwon_supply_pressure_report.json
```

명령은 CSV의 월별 전체값과 유형별 합계가 일치하는지 검증한 뒤, 최신 12개월을 기본 분석 기간으로 선택합니다. `자연관광`·`역사관광`은 문화관광으로 통합하고 `기타관광`은 원본에 보존하되 공급압력 계산에서 제외합니다. Peer CSV를 같은 형식으로 추가하면 다음 단계에서 Peer 비교와 percentile 산출에 활용할 수 있습니다.

AI 파일럿 리포트는 공급압력 결과와 확인된 Peer 사례를 분리해 처리합니다. `OPENAI_API_KEY`는 `.env` 또는 배포 환경변수에만 설정하고 브라우저에 노출하지 않습니다. 기본 모델은 `gpt-5.6-luna`입니다.

```bash
python3 -m pip install -e '.[ai]'

# Peer가 확정되기 전에는 사례 없이 잠정 정량 리포트만 생성합니다.
hankkeut-ai-tourism-report \
  --supply-pressure-report data/analysis/datalab_navigation/suwon_supply_pressure_report.json \
  --output data/analysis/ai_reports/suwon_pilot_report.json

# Peer 확정 후에만 웹 사례 검색을 켭니다. 허용 출처만 모델에 전달됩니다.
hankkeut-ai-tourism-report \
  --supply-pressure-report data/analysis/datalab_navigation/suwon_supply_pressure_report.json \
  --peer-region 강릉시 --peer-region 전주시 \
  --search-cases \
  --output data/analysis/ai_reports/suwon_pilot_report.json
```

구조적 Peer 후보는 SGIS 실데이터와 전국 TourAPI 지역 마스터로 산출합니다. Peer 후보는 아직 성과가 검증된 `우수 Peer`가 아니며, 다음 단계에서 데이터랩 월별 수요와 공급압력·성과를 결합해 선별합니다.

```bash
# Peer 분석 의존성 설치
python3 -m pip install -e data/analysis/similarity

# 최초 한 번: 전국 지역 마스터용 원본을 캐시한다.
tourgap-collect --all

# SGIS 실데이터로 구조적 후보 5개를 생성한다.
tourgap --region 수원시 --peer-k 5 \
  --output data/analysis/peer_candidates/suwon_structural_peer_candidates.json

# 각 후보에 내려받아야 할 데이터랩 월별 CSV 목록을 생성한다.
hankkeut-datalab-peer-manifest \
  --peer-result data/analysis/peer_candidates/suwon_structural_peer_candidates.json \
  --output data/analysis/datalab_navigation/suwon_peer_navigation_input_manifest.json
```

경기도 분석 기준은 [경기도 분석 가이드](docs/methodology/gyeonggi-analysis-guide.md)에 정리되어 있습니다. 실행 결과는 `results/`에 생성하며, 팀 공유용 해석 문서는 `docs/results/`에 작성합니다.

## 데이터 관리 원칙

- `data/reference/`: 행정구역 코드, 콘텐츠 분류표, 입력 템플릿 등 기준 데이터
- `data/raw/`: API 원본 응답. 대용량·재수집 가능 파일은 Git에 올리지 않음
- `data/interim/`: 정제·결합 중간 데이터
- `data/analysis/`: 분석을 재현하기 위해 공유할 입력 데이터
- `results/`: 실행 때마다 생성되는 CSV·JSON 결과

테스트는 다음 명령으로 실행합니다.

```bash
python3 -m unittest discover -s tests -q
```
