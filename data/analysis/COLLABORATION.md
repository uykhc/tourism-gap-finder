# 협업 지침 — 韓끗 관광 공백 분석

2026-08-18

## 1. 구조와 역할

```
repo/
  COLLABORATION.md      이 문서
  contracts/            공용 계약 패키지 (타입·Protocol·지역 마스터)
  <A의 폴더>/            A — 과제 1
  <B의 폴더>/            B — 과제 2
```

| 과제 | 내용 | 담당 | 구현할 것 |
|---|---|---|---|
| 1 | 특성지표 정의 및 특성 벡터화 | A | `PeerFinder` |
| 2 | 평가지표 및 평가 수식 정의 | B | `PerformanceEvaluator` |
| 3 | 공백 정의 | A+B | `GapAnalyzer` |

**A와 B는 서로를 import하지 않는다. 둘 다 `contracts`만 의존한다.**
과제 3에서 두 구현체를 주입해 합친다.

```
      contracts (Protocol)
        ↑            ↑
   A의 구현      B의 구현
        └──→ 과제 3 ←──┘
```

> 바꿀 수 없는 조건이 비슷한 지역끼리 비교해서, 바꿀 수 있는 관광 콘텐츠의 차이를 찾는다.

과제 1 = 바꿀 수 없는 조건 · 과제 2 = 관광의 결과 · 과제 3 = 바꿀 수 있는 콘텐츠.

용어는 `target`(입력지역) · `peer`(유사지역) · `benchmark`(우수 유사지역) · `gap`(공백)으로 통일.

---

## 2. 원칙

**P1. 한 변수는 과제 1·2·3 중 한 곳에만 등장한다.**
과제 3의 출력이 "체험 부족"인데 과제 1의 입력에 체험 비율을 넣으면,
체험이 비슷한 지역만 peer로 뽑혀 그 부족은 발견될 수 없다.

판정: `관광 정책의 결과로 변하는 값인가?` → 예: 과제 2·3 (과제 1 금지)
　　　`관광 콘텐츠의 양·종류인가?` → 예: 과제 3 전용 / 아니오: 과제 1 후보

**P2. `region_id`가 유일한 키다.** (§5)

**P3. `contracts`는 합의 없이 바꾸지 않는다.** 각자 폴더 내부는 전부 자유.

**P4. 값의 출처를 표기한다.** `real` / `proxy` / `static_reference` / `mock`.

**P5. 인과를 주장하지 않는다.** "비슷한 여건의 우수 지역에서 반복 관찰되는 차이"까지만.

---

## 3. 변수 소유권

새 변수는 여기 먼저 등록한다. P1의 실행 장치다.

| 과제 1 (A) | 과제 2 (B) | 과제 3 (공동) |
|---|---|---|
| 인구·면적·밀도 | 방문자 규모·증감률·구성비 | 콘텐츠 유형별 공급량 |
| 해안·도서 여부 | 계절·요일 방문 패턴 | (개수/구성비/인구당/면적당) |
| 농가·임가·어가 비율 | 체류·소비 강도 *(미공개)* | EX 체험 · VE 문화 · LS 레저 |
| 대도시 접근성 | 관광 다양성 *(미공개)* | EV 축제 · SH 쇼핑 · FD 음식 · AC 숙박 |
| 평균연령·가구 구조 | | NA 자연 · HS 역사 → 맥락 전용 |

### 회색지대 — 기본 판정

| 항목 | 판정 |
|---|---|
| 사업체·종사자 수 | **A**. 단 '관광 업종'만 골라내면 과제 3 침범이므로 전체만 |
| 계절·요일 방문 패턴 | **B**. 방문 데이터 파생이므로 성과 쪽 |
| 인구를 분모로 쓴 성과 지표 | **B 가능**. 인구 자체를 점수 항목으로 쓰는 것은 금지 |
| 숙박시설 **개수** | **과제 3**. B는 '숙박 방문객 비율' 같은 수요 측 지표를 쓴다 |

---

## 4. 인터페이스 계약

`contracts` 패키지가 계약의 전부다. 양쪽 모두 `pip install -e ./contracts` 후 사용한다.
**로직은 넣지 않는다** — 타입, Protocol, 스키마 검증, 지역 마스터뿐이다.

```python
# contracts/hankkeut_contracts/__init__.py
from __future__ import annotations
from typing import Protocol, Sequence
import pandas as pd

RegionId = str          # 법정동 시군구 코드 5자리 (예: "47130")

PEER_COLUMNS = ["rank", "region_id", "similarity"]
PERFORMANCE_COLUMNS = ["region_id", "performance_score"]
GAP_COLUMNS = ["rank", "category", "gap_score"]


class PeerFinder(Protocol):
    """과제 1 — 구조적 여건이 비슷한 지역을 찾는다."""

    def find_peers(
        self, target_region_id: RegionId, *, k: int | None = None
    ) -> pd.DataFrame:
        """PEER_COLUMNS 를 포함하는 표.

        rank        1부터
        region_id   peer의 region_id
        similarity  0~1, 클수록 유사

        - target 자신은 포함하지 않는다
        - 0~k행 가변. 호출부는 개수를 가정하지 않는다
        - 컬럼 추가는 자유
        """


class PerformanceEvaluator(Protocol):
    """과제 2 — 관광 성과를 채점하고 benchmark를 고른다."""

    def score(self, region_ids: Sequence[RegionId]) -> pd.DataFrame:
        """PERFORMANCE_COLUMNS 를 포함하는 표.

        performance_score  클수록 우수. 스케일은 자유
        지표 원값 컬럼 추가는 자유 (리포트·검증에 쓰인다)
        - 점수를 낼 수 없는 지역은 행을 빼거나 NaN. 0으로 채우지 않는다
        """

    def select_benchmarks(
        self,
        target_region_id: RegionId,
        peer_region_ids: Sequence[RegionId],
        *,
        k: int | None = None,
    ) -> list[RegionId]:
        """peer 중 target보다 성과가 높은 상위 k개.

        - peer_region_ids 밖의 지역을 절대 반환하지 않는다
        - target보다 성과가 낮은 지역을 반환하지 않는다
        - 조건을 만족하는 곳이 없으면 빈 목록. 이 계약을 없애면 과제 3이 깨진다
        """


class GapAnalyzer(Protocol):
    """과제 3 — 아직 확정 아님. 합류 시점에 함께 정한다."""

    def find_gaps(
        self, target_region_id: RegionId, benchmark_region_ids: Sequence[RegionId]
    ) -> pd.DataFrame: ...


def validate(frame: pd.DataFrame, columns: list[str], name: str) -> pd.DataFrame:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise ValueError(f"{name}에 필수 컬럼이 없습니다: {missing}")
    return frame


def load_regions() -> pd.DataFrame:
    """지역 마스터. region_id, province_name, region_name, admin_type.

    A가 생성해 contracts/hankkeut_contracts/data/regions.csv 로 커밋한다.
    B는 이걸 그대로 쓴다. 각자 만들면 지역 수가 어긋난다(230 vs 250 vs 264).
    """
    from pathlib import Path
    path = Path(__file__).parent / "data" / "regions.csv"
    return pd.read_csv(path, dtype={"region_id": str})
```

### 사용

```python
# A의 폴더
from hankkeut_contracts import PeerFinder, PEER_COLUMNS, validate

class TourgapPeerFinder:                       # Protocol이라 상속 불필요
    def find_peers(self, target_region_id, *, k=None):
        ...
        return validate(frame, PEER_COLUMNS, "peers")

# B의 폴더
from hankkeut_contracts import PerformanceEvaluator, load_regions

class MyEvaluator:
    def score(self, region_ids): ...
    def select_benchmarks(self, target_region_id, peer_region_ids, *, k=None): ...

# 과제 3 — 두 구현체를 주입해 합친다
peers = finder.find_peers(target)
benchmarks = evaluator.select_benchmarks(target, peers["region_id"].tolist())
gaps = analyzer.find_gaps(target, benchmarks)
```

### 규칙

- **Protocol이므로 상속하지 않는다.** 같은 시그니처면 된다.
- 반환 컬럼 **추가는 자유**, 필수 컬럼 삭제·개명은 합의.
- 자기 구현체가 `validate()`를 통과하는지 테스트로 확인한다.
- A가 설계를 바꾸면 B의 결과 숫자가 바뀐다. 정상이다.
  B는 특정 지역의 benchmark를 고정하지 말고 **방법론**을 검증한다.
  B의 테스트는 A의 구현 대신 **가짜 `PeerFinder`(표본 DataFrame 반환)** 로 짠다.

---

## 5. `region_id`

법정동 시군구 코드 5자리(경주시 `47130`). 전국 230개. `load_regions()`가 유일한 출처다.

- **지역명으로 조인 금지** — 중구·동구 5곳, 서구·남구·북구 4곳, 강서구·고성군 2곳
- 코드가 안 맞으면 이름으로 잇되 **반드시 시도 범위를 좁힌다**
- 일반구(청주시 흥덕구)는 모 시에 합친다. **끝자리 숫자로 판별 금지** —
  증평군(43745)은 끝자리 5인 군이다. 주소에 `○○시 ○○구`가 함께 나올 때만 합친다
- 2026년 개편 반영: 광주+전남 → 전남광주통합특별시(prefix `12`), 인천 구 개편.
  **낯선 지역명은 버그가 아니라 실제 데이터다**

API마다 코드 체계가 다르다. 변환은 각자 폴더에서 처리하고 계약에는 `region_id`만 오간다.

| 체계 | 부산 | 경주시 |
|---|---|---|
| 법정동 = `region_id` | 26 | 47130 |
| TourAPI areaCode | 6 | 35-2 |
| SGIS 인구/경계 API | 21 | 37020 *(군 지역은 둘이 또 다름)* |
| DataLab | 개편 이전 코드 | 47130 |

---

## 6. 각자 범위

### A — 과제 1 · `PeerFinder`

현재: 11개 구조 변수 → log 변환 → z-표준화 → 그룹 가중치 → 가중 유클리드 →
`similarity = exp(−d)` → 동일 행정유형 필터 → 상위 k.
가중치 규모 30 / 자연·지리 30 / 접근성 20 / 인구특성 20.

개선 과제 (근거 `hankkeut-proto/docs/peer-validation.md`):

1. **자치구 변별력 부족** — 서울 25개구 상호 유사도 중앙값 0.67. 상업·업무 변수 부재.
   SGIS 응답에 이미 있는 `corp_cnt`·`employee_cnt`·`tot_house`·`oldage_suprt_per` 활용 검토
2. **고유 지역 품질 급락** — 15번째 peer 유사도 0.4 미만이 21곳(9%). k 고정 대신 유사도 하한
3. **접근성이 직선거리 proxy** — 변수 1개가 20%를 독점

금지: 관광 콘텐츠 수·구성비, 방문자·체류·소비를 변수로 사용

산출물: `PeerFinder` 구현체 · `regions.csv` 생성 · 검증 문서
(무작위 대비 변별력 / 가중치 민감도 / 상호 peer 비율 / 스팟체크)

### B — 과제 2 · `PerformanceEvaluator`

`hankkeut-proto`의 성과 코드는 임시 구현이다. 참고하지 않고 새로 만든다.
지켜야 할 것은 §4 Protocol과 P1뿐이다.

설계할 때 답해야 할 질문:

1. **규모 편향 제거** — 방문자 절대량을 쓰면 peer 중 가장 큰 도시가 항상 benchmark가 된다.
   그러면 성과가 아니라 크기를 재는 것이다
2. **방문자 ≠ 관광객** — 이동통신 기반 일별 순방문자. 2박 3일이면 3일로 잡힌다
3. **지표 간 중복** — 다른 이름의 지표가 같은 것을 재고 있지 않은지
4. **benchmark 개수** — 한 곳만 쓰면 그 지역의 우연한 특성을 정답으로 오인한다. 3~5 권장
5. **미공개 지표가 열릴 때** 수식을 갈아엎지 않고 추가할 수 있는 구조인가

금지: 콘텐츠 공급량, 인구·면적을 점수 항목으로 사용(분모는 허용)

산출물: `PerformanceEvaluator` 구현체 · 검증 문서
(규모 편향 검사 = benchmark가 peer 중 최대 지역과 일치하는 비율 / 지표 간 상관행렬 /
지표 제거 민감도 / 안면타당도 = 강릉·경주·여수 등이 상위인지)

---

## 7. 과제 3 합류

착수 조건 — 완벽할 필요는 없고 더 이상 흔들리지 않으면 된다.

- A·B 각자 구현체가 `validate()`를 통과하고 검증 문서가 나옴
- `regions.csv` 최신
- §3 대장이 최신 — 과제 3에서 쓸 수 있는 변수(=1·2에서 안 쓴 것)가 명확해야 한다

그때 `GapAnalyzer`를 확정하고 함께 정할 것: 공백 비교의 중심 지표
(구성비/인구당/면적당 — **지표에 따라 결론이 달라진다**) · 대분류까지인지 중분류까지인지 ·
benchmark 0개일 때 무엇을 보여줄지 · 수요 데이터가 끝내 안 열릴 경우 공급 격차만으로 갈지.

지금 지켜둘 것: A는 유사성 변수에 콘텐츠 항목을 넣지 않는다. B는 성과 지표에 공급량을 넣지 않는다
— 넣으면 "공급이 많아 성과가 좋다고 판정된 지역과 비교해 공급이 적다"는 동어반복이 된다.

---

## 8. 코딩 에이전트 지시문

### A용

```
나는 공통 레포의 hankkeut-proto/ 에서 '과제 1: 특성지표 정의 및 특성 벡터화'를 담당한다.
../COLLABORATION.md 와 docs/peer-validation.md 를 먼저 읽어라.
기존 구현을 발전시키는 것이지 새로 만드는 게 아니다.

경계:
- hankkeut-proto/ 밖은 수정하지 마라. B의 폴더는 절대 건드리지 마라.
- ../contracts/ 는 공용 계약이다. 합의 없이 고치지 마라.
  단 regions.csv 는 내가 생성해 갱신한다.
- 성과·공백 코드(performance.py, supply.py, gap.py)는 이번 과제 범위가 아니다.

계약:
- hankkeut_contracts.PeerFinder 를 만족하는 구현체를 제공한다.
    find_peers(target_region_id, *, k=None) -> DataFrame
    필수 컬럼: rank, region_id, similarity   (추가는 자유)
- target 자신을 포함하지 마라. 반환 개수는 가변이어도 된다.
- validate(frame, PEER_COLUMNS, "peers") 를 통과하는지 테스트로 확인해라.

규칙:
- 유사성 변수에 관광 콘텐츠 수·구성비·방문자·체류·소비를 절대 넣지 마라.
  판정: "이 값이 관광 정책의 결과로 변하는가?" 그렇다면 넣지 마라.
- 조인 키는 region_id(법정동 5자리)다. 지역명으로 조인하지 마라.
- 새 변수를 추가하면 COLLABORATION.md §3 대장에도 등록해라.
- tests/test_no_leakage.py 가 실패하면 테스트를 고쳐서 통과시키지 마라.
  그 변수가 정말 유사성에 들어가도 되는지 먼저 판단하고 근거를 설명해라.

확인:
  python3 -m unittest discover -s tests
  tourgap --region 당진시 --no-save
  tourgap --region 강남구 --no-save     (자치구 변별력)
```

### B용

```
나는 공통 레포의 내 폴더에서 '과제 2: 평가지표 및 평가 수식 정의'를 담당한다.
../COLLABORATION.md 를 먼저 읽어라.
내 베이스 코드로 새로 만든다. hankkeut-proto/ 의 성과 코드는 임시 구현이니 참고하지 마라.

경계:
- 내 폴더 밖은 수정하지 마라. hankkeut-proto/ 는 절대 건드리지 마라.
- ../contracts/ 는 공용 계약이다. 합의 없이 고치지 마라.
- pip install -e ../contracts 로 설치해 쓴다.

계약: hankkeut_contracts.PerformanceEvaluator 를 만족하는 구현체를 제공한다.
    score(region_ids) -> DataFrame
        필수 컬럼: region_id, performance_score (클수록 우수, 스케일 자유)
    select_benchmarks(target_region_id, peer_region_ids, *, k=None) -> list[str]
        - peer_region_ids 밖의 지역을 절대 반환하지 마라
        - target보다 성과가 낮은 지역을 반환하지 마라
        - 조건을 만족하는 곳이 없으면 빈 목록. 이 경우를 반드시 처리해라
        - peer 개수는 가변이다. 15개 고정으로 가정하지 마라

규칙:
- 성과 지표는 '관광의 결과'만 쓴다. 관광자원 개수·구성비는 절대 금지(과제 3 영역).
  인구·면적은 분모로는 되지만 점수 항목으로는 쓰지 마라.
- 결측을 0으로 채우지 마라. 0은 '성과 바닥'이 되어 순위를 왜곡한다.
- 지역 마스터를 새로 만들지 말고 hankkeut_contracts.load_regions() 를 써라.
  DataLab은 개편 이전 코드를 쓰므로 region_id 매핑이 필요하다.
- AreaTarDemDsService / AreaTarResDemService / AreaTarDivService 는 등록은 됐지만
  전 지역·전 기간 0건을 반환한다. 파라미터 문제가 아니니 추측하며 헤매지 마라.
- 테스트는 A의 구현 대신 가짜 PeerFinder(표본 DataFrame 반환)로 짜라.
  A가 설계를 바꾸면 깨진다.
- 새 지표를 추가하면 COLLABORATION.md §3 대장에도 등록해라.
```

### 흔한 실수

1. 상대 폴더나 contracts/ 를 '개선'한다
2. 테스트를 고쳐서 통과시킨다 (특히 누출 방지 테스트)
3. 지역명으로 조인한다 — 중구가 5곳이라 값이 섞인다
4. API 필드명을 추측한다
5. 결측을 0으로 채운다 — 순위가 뒤집힌다
6. 지역 마스터를 각자 만든다 — 지역 수가 어긋난다
7. Protocol을 상속하려 든다 — 같은 시그니처면 충분하다
8. 낯선 지역명을 버그로 판단한다 — '전남광주통합특별시'는 실제 개편 결과다
