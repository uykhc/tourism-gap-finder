"""peer group 안에서 관광 성과가 좋은 지역(benchmark)을 고른다.

원칙 4: 전국 1등과 비교하지 않는다. 후보는 이미 peer group으로 좁혀져
있으므로 여기서는 그 안의 순위만 매긴다.

표준화 범위(config.performance.normalize_scope):
  national  전국 분포로 z를 낸다(기본). peer 15개로 z를 내면 표본이 작아
            점수가 크게 튄다. 후보가 peer로 제한돼 있으므로 전국 z를 써도
            서울·부산이 benchmark가 되는 일은 생기지 않는다.
  peer      명세 원문대로 peer group 내부에서 표준화한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import get_config
from .sources.kto_performance import PERFORMANCE_COLUMNS


def available_metrics(performance: pd.DataFrame) -> list[str]:
    """실제로 값이 있는 성과 지표만 고른다.

    체류·소비 강도처럼 아직 데이터가 없는 지표는 전부 결측이라 여기서
    빠지고, 남은 지표끼리 가중치가 다시 정규화된다.
    """
    usable = []
    for column in PERFORMANCE_COLUMNS:
        if column not in performance.columns:
            continue
        values = pd.to_numeric(performance[column], errors="coerce")
        if values.notna().any() and values.std(ddof=0) > 0:
            usable.append(column)
    return usable


def score_performance(
    performance: pd.DataFrame,
    peer_ids: list[str],
    target_region_id: str,
) -> pd.DataFrame:
    """peer + 입력지역의 성과 점수표. 입력지역도 함께 채점해 위치를 보여 준다."""
    config = get_config().performance
    columns = available_metrics(performance)
    if not columns:
        raise ValueError("사용할 수 있는 성과 지표가 없습니다.")

    # 목표 가중치를 '쓸 수 있는 지표'끼리 다시 정규화한다.
    raw_weights = {c: config.weights.get(c, 0.0) for c in columns}
    total_weight = sum(raw_weights.values())
    if total_weight <= 0:
        raw_weights = dict.fromkeys(columns, 1.0)
        total_weight = float(len(columns))
    weights = {c: w / total_weight for c, w in raw_weights.items()}

    frame = performance.copy()
    basis = (
        frame
        if config.normalize_scope == "national"
        else frame[frame["region_id"].isin([*peer_ids, target_region_id])]
    )

    scored = frame[["region_id"]].copy()
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        reference = pd.to_numeric(basis[column], errors="coerce")
        if column in config.log_scaled:
            values = np.log1p(values.clip(lower=0))
            reference = np.log1p(reference.clip(lower=0))
        mean = reference.mean()
        std = reference.std(ddof=0)
        z = (values - mean) / std if std and not np.isnan(std) else values * 0.0
        # 결측은 전국 평균(z=0)으로 두어 점수를 왜곡하지 않게 한다.
        scored[f"z_{column}"] = z.fillna(0.0)
        scored[column] = pd.to_numeric(frame[column], errors="coerce")

    scored["performance_score"] = sum(
        scored[f"z_{column}"] * weight for column, weight in weights.items()
    )
    scored.attrs["metrics_used"] = weights

    subset = scored[scored["region_id"].isin([*peer_ids, target_region_id])]
    result = subset.sort_values("performance_score", ascending=False).reset_index(
        drop=True
    )
    result.attrs["metrics_used"] = weights
    return result


def select_benchmarks(
    scored: pd.DataFrame,
    target_region_id: str,
    *,
    k: int | None = None,
) -> list[str]:
    """입력 지역보다 성과가 **높은** peer 중 상위 k개.

    단순히 상위 k개를 뽑으면 안 된다. 입력 지역이 이미 peer group에서
    1위인 경우, 자기보다 성과가 낮은 지역이 '롤모델'로 뽑혀 버린다.
    그 지역들과의 콘텐츠 차이는 배울 점이 아니므로 애초에 비교 대상이
    될 수 없다(원칙 4: 비슷한 조건에서 '잘하는' 지역과 비교한다).

    조건을 만족하는 지역이 k개보다 적으면 적은 대로 돌려주고,
    하나도 없으면 빈 목록을 돌려준다. 그 처리는 호출부에서 한다.
    """
    k = k if k is not None else get_config().performance.benchmark_k
    target_row = scored[scored["region_id"] == target_region_id]
    if target_row.empty:
        raise LookupError(f"{target_region_id} 의 성과 점수가 없습니다.")
    target_score = float(target_row["performance_score"].iloc[0])

    candidates = scored[
        (scored["region_id"] != target_region_id)
        & (scored["performance_score"] > target_score)
    ]
    return candidates.nlargest(k, "performance_score")["region_id"].tolist()


def target_rank(scored: pd.DataFrame, target_region_id: str) -> tuple[int, int]:
    """peer group 안에서 입력 지역이 몇 등인지."""
    ordered = scored.sort_values("performance_score", ascending=False)
    ids = ordered["region_id"].tolist()
    return ids.index(target_region_id) + 1, len(ids)
