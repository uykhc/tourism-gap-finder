"""관광 콘텐츠 공백 산정.

    supply_gap    = max(benchmark 대표값 - 입력지역 값, 0)
    relative_gap  = supply_gap / (benchmark 대표값 + eps)
    consistency   = benchmark 중 입력지역보다 공급이 많은 지역의 비율
    demand_mult   = 수요 보정 (없으면 1.0)
    gap_score     = relative_gap * consistency * demand_mult

consistency를 곱하는 이유(명세 §9): benchmark 한 곳만 유난히 많아서 생긴
격차와, 네 곳 모두에서 일관되게 나타나는 격차를 구분하기 위해서다.
앞쪽은 그 지역의 특수성일 가능성이 높다.

supply_gap을 0으로 clip하는 이유: 공급이 남는 카테고리(gap<0)에 낮은 수요
점수(<1)를 곱하면 부호가 뒤집혀 상위로 올라온다. 공백이 아닌 항목이
공백 1순위로 표시되는 사고를 막는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import GAP_CATEGORIES, LCLS1_NAMES, get_config


def calculate_gap(
    supply: pd.DataFrame,
    target_region_id: str,
    benchmark_ids: list[str],
    demand: pd.DataFrame | None = None,
    *,
    metric: str | None = None,
    categories: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """카테고리별 공백 점수표."""
    metric = metric or get_config().gap.primary_metric
    categories = categories if categories is not None else GAP_CATEGORIES
    epsilon = get_config().gap.epsilon

    subset = supply[supply["category"].isin(categories)]
    target = subset[subset["region_id"] == target_region_id].set_index("category")
    benchmarks = subset[subset["region_id"].isin(benchmark_ids)]

    aggregate = get_config().gap.aggregate
    bench_values = benchmarks.groupby("category")[metric].agg(aggregate)

    rows = []
    for category in categories:
        target_value = float(target[metric].get(category, 0.0) or 0.0)
        bench_value = float(bench_values.get(category, 0.0) or 0.0)

        supply_gap = max(bench_value - target_value, 0.0)
        relative_gap = supply_gap / (bench_value + epsilon)

        peer_values = benchmarks[benchmarks["category"] == category][metric]
        peer_values = pd.to_numeric(peer_values, errors="coerce").dropna()
        consistency = (
            float((peer_values > target_value).mean()) if len(peer_values) else 0.0
        )

        multiplier, demand_label = _demand_multiplier(
            demand, target_region_id, category
        )

        rows.append(
            {
                "category": category,
                "category_name": LCLS1_NAMES.get(category, category),
                "target_value": target_value,
                "benchmark_value": bench_value,
                "supply_gap": supply_gap,
                "relative_gap": relative_gap,
                "consistency": consistency,
                "demand_multiplier": multiplier,
                "demand_label": demand_label,
                "gap_score": relative_gap * consistency * multiplier,
            }
        )

    frame = (
        pd.DataFrame(rows)
        .sort_values("gap_score", ascending=False)
        .reset_index(drop=True)
    )
    frame.insert(0, "rank", range(1, len(frame) + 1))
    return frame


def _demand_multiplier(
    demand: pd.DataFrame | None, region_id: str, category: str
) -> tuple[float, str]:
    """수요 보정 계수와 라벨.

    수요 데이터가 없으면 1.0으로 두고 '미적용'이라고 표시한다.
    가짜 수요 점수를 지어내면 순위가 근거 없이 흔들리기 때문이다.
    """
    if demand is None or demand.empty:
        return 1.0, "미적용"

    match = demand[
        (demand["region_id"] == region_id) & (demand["category"] == category)
    ]
    if match.empty:
        return 1.0, "미적용"

    percentile = pd.to_numeric(match["demand_percentile"].iloc[0], errors="coerce")
    if pd.isna(percentile):
        return 1.0, "미적용"

    low, high = get_config().gap.demand_multiplier_range
    multiplier = float(np.clip(low + percentile, low, high))
    if percentile >= 0.66:
        label = "높음"
    elif percentile >= 0.33:
        label = "보통"
    else:
        label = "낮음"
    return multiplier, label


def drilldown(
    supply_lcls2: pd.DataFrame,
    target_region_id: str,
    benchmark_ids: list[str],
    parent_categories: list[str],
    lcls_names: dict[str, str],
    *,
    metric: str | None = None,
) -> pd.DataFrame:
    """상위 공백 대분류를 중분류로 쪼갠다.

    중분류는 표본이 작아 값이 튀므로, benchmark 합계가 너무 적은 항목은
    버린다. 대분류 결론을 뒤집는 용도가 아니라 '어떤 종류인지' 좁히는
    참고 자료다.
    """
    metric = metric or get_config().gap.primary_metric
    frames = []

    for parent in parent_categories:
        children = sorted(
            {
                str(c)
                for c in supply_lcls2["category"].unique()
                if str(c).startswith(parent) and str(c) != parent
            }
        )
        if not children:
            continue

        subset = supply_lcls2[supply_lcls2["category"].isin(children)]
        benchmarks = subset[subset["region_id"].isin(benchmark_ids)]
        keep = (
            benchmarks.groupby("category")["raw_count"].sum()
            >= get_config().gap.drilldown_min_count
        )
        keep_categories = [c for c in children if keep.get(c, False)]
        if not keep_categories:
            continue

        frame = calculate_gap(
            subset,
            target_region_id,
            benchmark_ids,
            None,
            metric=metric,
            categories=tuple(keep_categories),
        )
        frame["parent"] = parent
        frame["parent_name"] = LCLS1_NAMES.get(parent, parent)
        frame["category_name"] = frame["category"].map(lambda c: lcls_names.get(c, c))
        frames.append(frame)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def context_table(
    supply: pd.DataFrame,
    target_region_id: str,
    benchmark_ids: list[str],
    categories: tuple[str, ...],
    *,
    metric: str | None = None,
) -> pd.DataFrame:
    """원천 자원(자연·역사) 비교표. 랭킹에는 넣지 않는다."""
    metric = metric or get_config().gap.primary_metric
    subset = supply[supply["category"].isin(categories)]
    target = subset[subset["region_id"] == target_region_id].set_index("category")
    bench = subset[subset["region_id"].isin(benchmark_ids)]
    bench_values = bench.groupby("category")[metric].agg(get_config().gap.aggregate)

    rows = []
    for category in categories:
        rows.append(
            {
                "category": category,
                "category_name": LCLS1_NAMES.get(category, category),
                "target_value": float(target[metric].get(category, 0.0) or 0.0),
                "benchmark_value": float(bench_values.get(category, 0.0) or 0.0),
            }
        )
    return pd.DataFrame(rows)
