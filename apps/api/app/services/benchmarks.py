"""비교 기준 지역(벤치마크) 선정.

`hankkeut_contracts.PerformanceEvaluator.select_benchmarks`는 "유사 지역 중
성과가 대상보다 높은 곳"으로 정의되어 있지만, 전국 성과 점수가 아직 없다.
그래서 지금은 비교 데이터가 확보된 구조적 유사 지역을 비교 기준으로 쓰고,
그 사실을 `performance_backed`로 표시해 응답 문구와 `report_status`에 반영한다.

성과 점수가 열리면 `_performance_backed_benchmarks`만 채우면 되고, 이 함수의
호출측은 바뀌지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import artifacts

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
    return BenchmarkSelection(
        regions=tuple(resolved[:limit]),
        performance_backed=False,
        unresolved_names=tuple(unresolved),
    )
