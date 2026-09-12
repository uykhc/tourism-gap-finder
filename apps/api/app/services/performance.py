"""관광 성과 점수와 우수 지역 선정.

`hankkeut_contracts.PerformanceEvaluator`의 두 메서드 중 `select_benchmarks`는
규칙만 문서에 있고 구현이 없었다(`COLLABORATION.md` §8). 그래서 보고서의 비교
기준 지역이 늘 비어 있었다. 여기서 그 규칙을 그대로 옮긴다.

`select_benchmarks`는 순수 함수다. 키도 네트워크도 쓰지 않고, `score()`가 무엇을
돌려주든 그것만으로 판단한다. 점수를 낼 수 없으면 빈 목록을 돌려주며, 이는
계약이 명시한 정상 경로다 — 없는 우수 지역을 만들어내지 않는다.
"""

from __future__ import annotations

from typing import Any, Protocol

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

    주의: 이 경로의 HTTP 클라이언트 두 개는 실제 키가 있어야 동작해 아직
    실행으로 확인하지 못했다. 키가 없으면 503이고, 응답이 부족하면 빈 dict를
    돌려 `select_benchmarks`가 계약대로 빈 목록을 내도록 한다.
    """

    def __init__(self, *, timeout_seconds: float = 30.0, page_size: int = 1000) -> None:
        self._timeout = timeout_seconds
        self._page_size = page_size

    def score(self, region_ids: list[str]) -> dict[str, float]:
        service_key = require_env(
            "VISITOR_API_SERVICE_KEY", "TOUR_API_SERVICE_KEY", feature="관광 성과 점수"
        )
        benchmark = require_module(
            "hankkeut_evaluation.visitor_portfolio_benchmark", feature="관광 성과 점수"
        )
        visitor_api = require_module(
            "hankkeut_calculation.tourism_data.visitor_api", feature="관광 성과 점수"
        )
        demand_api = require_module(
            "hankkeut_calculation.tourism_data.tourism_demand_api", feature="관광 성과 점수"
        )

        coded = _regions_with_codes(region_ids)
        if len(coded) < 2:
            # 비교 집단이 두 곳도 안 되면 백분위가 의미를 갖지 못한다.
            return {}

        try:
            demand_client = demand_api.TourismDemandApiClient(
                service_key, timeout_seconds=self._timeout, page_size=self._page_size
            )
            base_ym, demand_scores = benchmark.fetch_latest_common_demand_scores_by_area(
                demand_client,
                regions=tuple(_DemandRegion(area, sigungu) for area, sigungu in coded.values()),
                lookback_months=DEMAND_LOOKBACK_MONTHS,
            )
            visitor_client = visitor_api.VisitorApiClient(
                service_key, timeout_seconds=self._timeout, page_size=self._page_size
            )
            records = visitor_client.fetch_local_daily_visitors(
                start_ymd=f"{base_ym}01", end_ymd=benchmark._last_day_of_month(base_ym)
            )
        except Exception:  # noqa: BLE001 - 원천 API 실패는 점수 부재로 다룬다
            return {}

        names = {region_table.find_region(rid)["region_name"]: rid for rid in coded}
        visitor_rows, _ = benchmark.aggregate_daily_visitor_sums(
            records, allowed_region_names=set(names), visitor_type_names=()
        )
        try:
            scores = benchmark.build_regional_tourism_scores(
                visitor_rows,
                demand_scores,
                region_sigungu_codes={
                    region_table.find_region(rid)["region_name"]: (f"{area}:{sigungu}",)
                    for rid, (area, sigungu) in coded.items()
                },
                visitor_weight=VISITOR_WEIGHT,
                resource_demand_weight=RESOURCE_DEMAND_WEIGHT,
                demand_intensity_weight=DEMAND_INTENSITY_WEIGHT,
            )
        except ValueError:
            # 한 지역이라도 방문자 수가 없으면 집단 백분위를 낼 수 없다.
            return {}
        return {
            names[item.region_name]: float(item.composite_score)
            for item in scores
            if item.region_name in names and item.composite_score is not None
        }


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


def _regions_with_codes(region_ids: list[str]) -> dict[str, tuple[str, str]]:
    """TourAPI 코드와 지역 정보가 모두 있는 지역만 남긴다.

    2026년 개편으로 신설된 구는 TourAPI 코드가 없다. 옛 자치구 코드를 빌려
    쓰면 서로 다른 지역에 같은 수요값이 붙으므로 아예 제외한다.
    """
    coded: dict[str, tuple[str, str]] = {}
    seen_names: set[str] = set()
    for region_id in dict.fromkeys(region_ids):
        region = region_table.find_region(region_id)
        code = region_table.tour_api_code(region_id)
        if region is None or code is None:
            continue
        # 방문자 API는 지역명으로만 조인된다. 같은 집단에 동명이 있으면 어느
        # 쪽 값인지 알 수 없으므로 둘 다 뺀다.
        name = region["region_name"]
        if name in seen_names:
            coded = {rid: value for rid, value in coded.items()
                     if region_table.find_region(rid)["region_name"] != name}
            continue
        seen_names.add(name)
        coded[region_id] = code
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
