"""비교 기준 지역(벤치마크) 선정.

먼저 성과 점수로 "유사 지역 중 성과가 대상보다 높은 곳"을 고른다
(`performance.select_benchmarks`). 점수를 낼 수 없으면 — 키가 없거나 원천
응답이 부족하면 — 비교 데이터가 확보된 구조적 유사 지역으로 내려간다.

둘 중 어느 경로를 탔는지는 `performance_backed`가 들고 있고, 그 값이 응답의
`methodology.benchmark_selection_*` 문구와 `report_status`를 결정한다. 성과
검증을 거치지 않은 비교를 '우수 지역'이라고 부르지 않기 위한 구분이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

from . import artifacts, performance

#: 비교 기준 지역 수 상한. COLLABORATION.md §6의 "최대 3곳"을 따른다.
DEFAULT_BENCHMARK_COUNT = 3

_STRUCTURAL_RULE = (
    "관광 성과 데이터가 전국 단위로 열리기 전이므로, 구조적 유사도 상위 지역 중 "
    "공급 비교 데이터가 확보된 지역을 비교 기준으로 사용합니다."
)
_STRUCTURAL_NOTE = (
    "성과 검증을 거친 우수 지역이 아닙니다. 구조적으로 비슷한 여건을 가진 비교 "
    "후보이며, 성과 데이터가 확보되면 다시 선정합니다."
)

_PERFORMANCE_RULE = (
    "구조적 유사도 상위 10개 지역 중 관광 성과 복합점수가 높은 상위 "
    f"{DEFAULT_BENCHMARK_COUNT}곳입니다."
)
_PERFORMANCE_NOTE = (
    "복합점수는 이동통신 기반 방문자 수 40%, 관광 자원 수요 30%, 관광 수요 강도 "
    "30%를 비교 집단 안에서 백분위로 환산해 합산한 값입니다."
)



@dataclass(frozen=True, slots=True)
class BenchmarkSelection:
    """선정된 비교 기준 지역과 그 선정 근거."""

    regions: tuple[dict[str, Any], ...] = ()
    performance_backed: bool = False
    rule: str = _STRUCTURAL_RULE
    note: str = _STRUCTURAL_NOTE
    unresolved_names: tuple[str, ...] = field(default=())

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(str(region["region_name"]) for region in self.regions)

    def by_name(self, region_name: str) -> dict[str, Any] | None:
        for region in self.regions:
            if region["region_name"] == region_name:
                return region
        return None


def resolve_benchmarks(
    region_id: str,
    relative_supply: dict[str, Any] | None,
    *,
    limit: int = DEFAULT_BENCHMARK_COUNT,
) -> BenchmarkSelection:
    """비교 기준 지역을 정한다.

    상대적 공급 산출물이 실제로 비교한 지역만 후보가 된다. 산출물에 수치가
    없는 지역을 비교 기준이라고 부르면 화면의 '비교 기준 n곳'이 실제 근거보다
    많아진다.
    """
    if relative_supply is None:
        return BenchmarkSelection()
    names = [
        str(item.get("region_name") or "").strip()
        for item in relative_supply.get("peer_regions", [])
        if isinstance(item, dict) and str(item.get("region_name") or "").strip()
    ]
    resolved, unresolved = artifacts.resolve_peer_regions(
        names, candidate_region_ids=artifacts.peer_region_ids(region_id)
    )
    # 대상 지역 자신은 비교 기준이 될 수 없다.
    resolved = [region for region in resolved if region["region_id"] != region_id]

    selected_ids, scored = _performance_backed_benchmarks(region_id, resolved, limit=limit)
    if selected_ids:
        order = {region_id_: index for index, region_id_ in enumerate(selected_ids)}
        return BenchmarkSelection(
            regions=tuple(sorted(
                (region for region in resolved if region["region_id"] in order),
                key=lambda region: order[region["region_id"]],
            )),
            performance_backed=True,
            rule=_PERFORMANCE_RULE,
            note=_PERFORMANCE_NOTE,
            unresolved_names=tuple(unresolved),
        )
    return BenchmarkSelection(
        regions=tuple(resolved[:limit]),
        performance_backed=False,
        rule=_STRUCTURAL_RULE,
        note=_STRUCTURAL_NOTE,
        unresolved_names=tuple(unresolved),
    )


def _performance_backed_benchmarks(
    region_id: str, resolved: list[dict[str, Any]], *, limit: int
) -> tuple[list[str], bool]:
    """`(후보 중 성과 점수 상위 지역, 점수를 낼 수 있었는지)`.

    계약상 빈 목록은 정상이다. 다만 '점수가 없어서 비었다'와 '점수는 있는데
    대상보다 높은 지역이 없어서 비었다'를 호출측이 구분할 수 있어야 한다.
    """
    if not resolved:
        return [], False
    peer_ids = [region["region_id"] for region in resolved]
    requested_ids = [region_id, *peer_ids]
    scores = _artifact_performance_scores(requested_ids)
    if scores:
        selected = _top_performance_regions(peer_ids, scores, limit)
        return selected, bool(selected)
    try:
        scorer = performance.default_scorer()
        scores = scorer.score(requested_ids)
        selected = _top_performance_regions(peer_ids, scores, limit)
    except HTTPException:
        # 키나 패키지가 없는 것은 오류가 아니다. 성과 기반 선정만 못 한다.
        return [], False
    return selected, True


def _top_performance_regions(
    peer_ids: list[str], scores: dict[str, float], limit: int
) -> list[str]:
    return sorted(
        (region_id for region_id in peer_ids if region_id in scores),
        key=lambda region_id: (-scores[region_id], region_id),
    )[:limit]


def _artifact_performance_scores(region_ids: list[str]) -> dict[str, float]:
    """Load precomputed scores without turning missing artifacts into zeroes."""
    scores: dict[str, float] = {}
    for region_id in region_ids:
        payload = artifacts.load_performance(region_id)
        performance_payload = payload.get("performance") if isinstance(payload, dict) else None
        value = (
            performance_payload.get("composite_score")
            if isinstance(performance_payload, dict)
            else None
        )
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            scores[region_id] = float(value)
    return scores


class _FixedScorer:
    """이미 받아 둔 점수를 그대로 돌려준다. 같은 요청에서 두 번 조회하지 않는다."""

    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    def score(self, region_ids: list[str]) -> dict[str, float]:
        return {key: value for key, value in self._scores.items() if key in region_ids}
