"""관광 성과 점수와 우수 지역 선정.

`hankkeut_contracts.PerformanceEvaluator`의 두 메서드 중 `select_benchmarks`는
규칙만 문서에 있고 구현이 없었다(`COLLABORATION.md` §8). 그래서 보고서의 비교
기준 지역이 늘 비어 있었다. 여기서 그 규칙을 그대로 옮긴다.

`select_benchmarks`는 순수 함수다. 키도 네트워크도 쓰지 않고, `score()`가 무엇을
돌려주든 그것만으로 판단한다. 점수를 낼 수 없으면 빈 목록을 돌려주며, 이는
계약이 명시한 정상 경로다 — 없는 우수 지역을 만들어내지 않는다.
"""

from __future__ import annotations

from typing import Any, ClassVar, Protocol

from . import regions as region_table
from .analysis_runtime import require_env, require_module

#: 비교 기준 지역 수 상한. COLLABORATION.md §6의 "3~5 권장" 중 하한을 쓴다.
DEFAULT_BENCHMARK_COUNT = 3

#: 성과 점수 가중치. config/gyeonggi/performance_evaluator.json과 같은 값이다.
VISITOR_WEIGHT = 0.4
RESOURCE_DEMAND_WEIGHT = 0.3
DEMAND_INTENSITY_WEIGHT = 0.3

#: 네 지표가 모두 있는 공통 연월을 찾을 때 거슬러 볼 개월 수.
DEMAND_LOOKBACK_MONTHS = 24


class Scorer(Protocol):
    """`region_id -> performance_score` 를 돌려준다. 낼 수 없으면 빈 dict."""

    def score(self, region_ids: list[str]) -> dict[str, float]: ...


class UnavailableScorer:
    """성과 점수를 낼 수 없을 때. 0으로 채우지 않고 아무것도 돌려주지 않는다."""

    def score(self, region_ids: list[str]) -> dict[str, float]:
        del region_ids
        return {}


def select_benchmarks(
    target_region_id: str,
    peer_region_ids: list[str],
    *,
    scorer: Scorer,
    k: int | None = None,
) -> list[str]:
    """유사 지역 중 성과가 대상보다 높은 곳을 고른다.

    `COLLABORATION.md` §8의 규칙을 그대로 지킨다.

    - `peer_region_ids` 밖의 지역을 반환하지 않는다
    - 대상보다 성과가 낮은 지역을 반환하지 않는다
    - 조건을 만족하는 곳이 없으면 빈 목록
    - peer 개수는 가변이다

    동점은 근거가 아니므로 제외한다. '대상보다 낮지 않다'가 아니라 '대상보다
    높다'가 조건이다.
    """
    candidates = [item for item in dict.fromkeys(peer_region_ids) if item != target_region_id]
    if not candidates:
        return []
    scores = scorer.score([target_region_id, *candidates])
    target_score = scores.get(target_region_id)
    if target_score is None:
        # 대상 점수가 없으면 '더 높다'를 판단할 수 없다. 결측을 0으로 보지 않는다.
        return []
    better = [
        (region_id, score)
        for region_id in candidates
        if (score := scores.get(region_id)) is not None and score > target_score
    ]
    better.sort(key=lambda item: (-item[1], item[0]))
    return [region_id for region_id, _ in better[: k or DEFAULT_BENCHMARK_COUNT]]


# ---------------------------------------------------------------------------
# 이동통신 방문자·관광 수요 기반 점수
# ---------------------------------------------------------------------------
class VisitorScorer:
    """`hankkeut_evaluation.visitor_portfolio_benchmark`로 성과 점수를 낸다.

    방문자 수 40% + 관광 자원 수요 30% + 관광 수요 강도 30%를 **주어진 집단
    안에서** 백분위로 환산해 합산한다. 백분위는 비교 집단이 있어야 의미가 있어
    대상 + peer 집합을 함께 넘긴다. 전국 일괄 경로(CLI `main()`)는 쓰지 않는다.

    조인은 전부 `region_id`(법정동 5자리)로 한다. 방문자 API 응답의
    `signguCode`가 곧 `region_id`이고, 수요지수 API는 별도의 법정동 코드 표
    (`services.regions.demand_codes`)로 조회한다. 지역명으로 조인하면 중구
    5곳이 한 덩어리가 된다.

    방문자 조회는 한 달치 전국 일별 데이터(하루 약 800행)를 받아오므로, 월
    단위로 캐시해 비교 집단이 달라져도 다시 받지 않는다. 실패는 캐시하지
    않는다.
    """

    #: 기준월별 캐시. 프로세스 안에서만 살고 실패는 담지 않는다.
    _visitor_cache: ClassVar[dict[tuple[str, str], dict[str, float]]] = {}
    _demand_cache: ClassVar[dict[tuple[str, tuple[str, ...]], tuple[str, dict[str, Any]]]] = {}

    def __init__(self, *, timeout_seconds: float = 45.0, page_size: int = 1000) -> None:
        self._timeout = timeout_seconds
        self._page_size = page_size

    def score(self, region_ids: list[str]) -> dict[str, float]:
        service_key = require_env(
            "VISITOR_API_SERVICE_KEY", "TOUR_API_SERVICE_KEY", feature="관광 성과 점수"
        )
        benchmark = require_module(
            "hankkeut_evaluation.visitor_portfolio_benchmark", feature="관광 성과 점수"
        )

        coded = _regions_with_codes(region_ids)
        if len(coded) < 2:
            # 비교 집단이 두 곳도 안 되면 백분위가 의미를 갖지 못한다.
            return {}

        try:
            base_ym, demand_scores = self._demand_scores(service_key, coded)
            visitor_sums = self._visitor_sums(service_key, base_ym)
        except Exception:  # noqa: BLE001 - 원천 API 실패는 점수 부재로 다룬다
            return {}

        # 방문자 수가 없는 지역이 있으면 build_regional_tourism_scores가 거부한다.
        # 그 지역만 빼고 남은 집단으로 계산한다.
        usable: dict[str, tuple[str, ...]] = {}
        visitor_rows: list[dict[str, Any]] = []
        for region_id, codes in coded.items():
            total = _visitor_total(region_id, codes, visitor_sums)
            if total is None:
                continue
            usable[region_id] = codes
            visitor_rows.append({
                "region_id": region_id,
                "region_name": region_id,
                "daily_visitor_sum": total,
            })
        if len(usable) < 2:
            return {}
        try:
            scores = benchmark.build_regional_tourism_scores(
                visitor_rows,
                demand_scores,
                region_sigungu_codes=usable,
                visitor_weight=VISITOR_WEIGHT,
                resource_demand_weight=RESOURCE_DEMAND_WEIGHT,
                demand_intensity_weight=DEMAND_INTENSITY_WEIGHT,
            )
        except (KeyError, ValueError):
            return {}
        return {
            item.region_id: float(item.composite_score)
            for item in scores
            if item.region_id and item.composite_score is not None
        }

    def _demand_scores(
        self, service_key: str, coded: dict[str, tuple[str, ...]]
    ) -> tuple[str, dict[str, Any]]:
        """네 지표가 모두 있는 최근 월과 그 월의 수요 점수."""
        demand_api = require_module(
            "hankkeut_calculation.tourism_data.tourism_demand_api", feature="관광 성과 점수"
        )
        benchmark = require_module(
            "hankkeut_evaluation.visitor_portfolio_benchmark", feature="관광 성과 점수"
        )
        # 필요한 (시도, 법정동코드) 쌍이 같으면 같은 응답이다.
        wanted = tuple(sorted({code for codes in coded.values() for code in codes}))
        cache_key = (service_key[-8:], wanted)
        cached = self._demand_cache.get(cache_key)
        if cached is not None:
            return cached
        client = demand_api.TourismDemandApiClient(
            service_key, timeout_seconds=self._timeout, page_size=self._page_size
        )
        regions = tuple(
            _DemandRegion(code.split(":", 1)[0], code.split(":", 1)[1]) for code in wanted
        )
        base_ym, scores = benchmark.fetch_latest_common_demand_scores_by_area(
            client, regions=regions, lookback_months=DEMAND_LOOKBACK_MONTHS
        )
        self._demand_cache[cache_key] = (base_ym, scores)
        return base_ym, scores

    def _visitor_sums(self, service_key: str, base_ym: str) -> dict[str, float]:
        """기준월 한 달간 지역별 일별 순방문자 수의 합. region_id로 묶는다."""
        cache_key = (service_key[-8:], base_ym)
        cached = self._visitor_cache.get(cache_key)
        if cached is not None:
            return cached
        visitor_api = require_module(
            "hankkeut_calculation.tourism_data.visitor_api", feature="관광 성과 점수"
        )
        benchmark = require_module(
            "hankkeut_evaluation.visitor_portfolio_benchmark", feature="관광 성과 점수"
        )
        client = visitor_api.VisitorApiClient(
            service_key, timeout_seconds=self._timeout, page_size=self._page_size
        )
        records = client.fetch_local_daily_visitors(
            start_ymd=f"{base_ym}01", end_ymd=benchmark._last_day_of_month(base_ym)
        )
        # 전국을 한 번에 받아 두면 비교 집단이 달라져도 재조회가 없다.
        # 개편 전 코드도 함께 허용한다. 개편이 반영되지 않은 달에는 광주·전남
        # 지역이 아직 옛 코드로만 공표되므로, 걸러 버리면 그 지역은 점수를
        # 낼 수 없다. `_visitor_total`이 이 값을 찾아 쓴다.
        allowed = set(region_table.all_region_ids()) | region_table.legacy_region_codes()
        rows, _ = benchmark.aggregate_daily_visitor_sums(records, allowed_region_ids=allowed)
        sums = {str(row["region_id"]): float(row["daily_visitor_sum"]) for row in rows}
        self._visitor_cache[cache_key] = sums
        return sums

    @classmethod
    def clear_caches(cls) -> None:
        cls._visitor_cache.clear()
        cls._demand_cache.clear()


class _DemandRegion:
    """`fetch_latest_common_demand_scores_by_area`가 기대하는 최소 모양."""

    __slots__ = ("definition",)

    def __init__(self, area_code: str, sigungu_code: str) -> None:
        self.definition = _DemandDefinition(area_code, sigungu_code)


class _DemandDefinition:
    __slots__ = ("area_code", "sigungu_code")

    def __init__(self, area_code: str, sigungu_code: str) -> None:
        self.area_code = area_code
        self.sigungu_code = sigungu_code


def _visitor_total(
    region_id: str, demand_keys: tuple[str, ...], visitor_sums: dict[str, float]
) -> float | None:
    """해당 지역의 방문자 합. 찾을 수 없으면 `None`.

    방문자 API가 쓰는 코드 집합은 행정구역 개편에 따라 월마다 다르다. 개편이
    반영되기 전 달에는 광주·전남 지역이 아직 옛 코드(순천시 `46150`)로 공표되고
    우리 표의 코드(`12150`)는 없다. 이때는 수요지수 표가 들고 있는 개편 전
    코드로 한 번 더 찾는다 — 같은 지역의 코드이므로 추측이 아니다.

    일반구가 있는 시는 시 단위 행이 그대로 있으므로 이 경로를 타지 않는다.
    구 단위 행을 더해 시를 만드는 일은 하지 않는다.
    """
    direct = visitor_sums.get(region_id)
    if direct is not None:
        return direct
    if len(demand_keys) != 1:
        return None
    legacy_code = demand_keys[0].split(":", 1)[1]
    if legacy_code == region_id:
        return None
    return visitor_sums.get(legacy_code)


def _regions_with_codes(region_ids: list[str]) -> dict[str, tuple[str, ...]]:
    """수요지수 API로 조회할 수 있는 지역만 `region_id → 조회 키`로 남긴다.

    조회 키는 `fetch_latest_common_demand_scores_by_area`가 돌려주는
    `"<시도>:<법정동코드>"` 형식이다. 일반구가 있는 시는 키가 여러 개이고
    `build_regional_tourism_scores`가 그 값들을 평균한다.

    동명 지역을 빼는 처리는 없다. 조인이 `region_id`로 이뤄지므로 서울 중구와
    부산 중구는 애초에 서로 다른 키다.
    """
    coded: dict[str, tuple[str, ...]] = {}
    for region_id in dict.fromkeys(region_ids):
        if region_table.find_region(region_id) is None:
            continue
        codes = region_table.demand_codes(region_id)
        if not codes:
            # 수요지수 API가 공표하지 않는 지역. 옛 코드를 빌려 쓰지 않는다.
            continue
        coded[region_id] = tuple(f"{code[:2]}:{code}" for code in codes)
    return coded


def default_scorer() -> Scorer:
    """키가 있으면 실제 점수를, 없으면 '점수 없음'을 쓴다."""
    from .analysis_runtime import has_env

    if has_env("VISITOR_API_SERVICE_KEY", "TOUR_API_SERVICE_KEY"):
        return VisitorScorer()
    return UnavailableScorer()


def score_regions(region_ids: list[str]) -> dict[str, Any]:
    """진단용. 지역별 성과 점수와 산출하지 못한 지역."""
    scores = default_scorer().score(region_ids)
    return {
        "scores": scores,
        "unavailable_region_ids": [item for item in region_ids if item not in scores],
    }
