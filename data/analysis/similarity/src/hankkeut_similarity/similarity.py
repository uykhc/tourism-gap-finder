"""유사성 feature 행렬.

원칙 1: 여기 들어가는 변수에는 관광 콘텐츠 구조가 없어야 한다.
공백의 output(콘텐츠 유형별 공급)을 유사지역 선정 input에 넣으면
찾으려는 공백을 미리 지워 버리기 때문이다.
원칙 2: 최대한 지역의 '구조적·외생적 조건'만 담는다.

tests/test_no_leakage.py 가 이 규칙을 자동으로 검사한다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SIMILARITY_FEATURES, get_config
from .feature_builder import (
    build_feature_table,
    normalize_feature_schema,
    preprocess_similarity_values,
)
from .sources.structural import metro_distance_km


def build_similarity_features(
    regions: pd.DataFrame,
    structural: pd.DataFrame,
    centroids: pd.DataFrame,
    coastal: pd.DataFrame,
) -> pd.DataFrame:
    """모델에 넣기 직전 상태의 feature 표."""
    geography = coastal.copy()
    if not centroids.empty:
        geography = geography.merge(centroids, on="region_id", how="left")

    frame = build_feature_table(
        regions,
        structural=structural,
        geography=geography,
    )

    frame["metro_distance_km"] = metro_distance_km(frame)

    return frame


def feature_columns() -> list[str]:
    """config가 지정한 유사성 feature 이름."""
    configured = {
        column
        for group in get_config().similarity.feature_groups.values()
        for column in group
    }
    return [column for column in SIMILARITY_FEATURES if column in configured]


def feature_weights(available_columns: list[str] | None = None) -> pd.Series:
    """feature별 가중치.

    그룹 weight를 그룹 안의 feature 수로 나눠 고르게 배분한 뒤
    전체 합이 1이 되도록 정규화한다. 그래야 '자연·지리 30%'라는 말이
    변수 개수와 무관하게 유지된다.
    """
    weights: dict[str, float] = {}
    groups = get_config().similarity.feature_groups
    group_weights = get_config().similarity.group_weights

    allowed = set(available_columns) if available_columns is not None else None
    for group_name, configured_columns in groups.items():
        columns = [
            column
            for column in configured_columns
            if allowed is None or column in allowed
        ]
        if not columns:
            continue
        share = group_weights.get(group_name, 0.0) / len(columns)
        for column in columns:
            weights[column] = share

    for column, weight in get_config().similarity.feature_weights.items():
        if column in weights:
            weights[column] = weight

    series = pd.Series(weights, dtype=float)
    total = series.sum()
    return series / total if total else series


def standardize(
    frame: pd.DataFrame, columns: list[str]
) -> tuple[pd.DataFrame, pd.Series]:
    """로그 변환 후 z-표준화. 결측은 결측으로 남긴다.

    sklearn StandardScaler와 같은 결과지만, 결측 처리와 컬럼 유지를
    직접 다루기 위해 pandas로 계산한다.
    """
    subset = preprocess_similarity_values(
        normalize_feature_schema(frame),
        columns,
        log_columns=get_config().similarity.log_transform_columns,
    )
    means = subset.mean()
    stds = subset.std(ddof=0).replace(0, np.nan)
    scaled = (subset - means) / stds
    return scaled, stds


def available_features(frame: pd.DataFrame) -> list[str]:
    """계산 가능한 feature 목록.

    전부 결측이거나 분산이 없는 컬럼은 거리 계산에서 제외한다. 개별
    지역의 결측은 pairwise 거리 계산에서 따로 처리한다.
    """
    normalized = normalize_feature_schema(frame)
    usable = []
    for column in feature_columns():
        if column not in normalized.columns:
            continue
        series = pd.to_numeric(normalized[column], errors="coerce")
        if series.notna().any() and series.std(ddof=0) > 0:
            usable.append(column)
    return usable
