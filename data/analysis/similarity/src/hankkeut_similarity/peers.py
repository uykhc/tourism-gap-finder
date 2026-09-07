"""유사 지역(peer) 탐색.

가중 Euclidean 거리로 k-nearest neighbors를 찾는다. 설명 가능성이
정확도보다 중요하므로 복잡한 모델을 쓰지 않는다. 대신 어떤 변수가
유사/상이 판단에 얼마나 기여했는지 함께 돌려준다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import get_config
from .feature_builder import normalize_feature_schema
from .similarity import available_features, feature_weights, standardize

try:
    from hankkeut_contracts import PEER_COLUMNS, validate
except ModuleNotFoundError:  # pragma: no cover - editable contracts 미설치 시 테스트 fallback
    PEER_COLUMNS = ["rank", "region_id", "similarity"]

    def validate(frame: pd.DataFrame, columns: list[str], name: str) -> pd.DataFrame:
        missing = [c for c in columns if c not in frame.columns]
        if missing:
            raise ValueError(f"{name}에 필수 컬럼이 없습니다: {missing}")
        return frame


class HankkeutSimilarityPeerFinder:
    """contracts.PeerFinder Protocol을 만족하는 유사 지역 탐색기."""

    def __init__(
        self,
        features: pd.DataFrame,
        *,
        default_k: int | None = None,
        min_similarity: float | None = None,
        same_admin_type: bool | None = None,
    ) -> None:
        self._features = normalize_feature_schema(features)
        self._default_k = default_k
        self._min_similarity = min_similarity
        self._same_admin_type = same_admin_type

    @classmethod
    def from_csv(
        cls,
        path: str,
        *,
        default_k: int | None = None,
        min_similarity: float | None = None,
        same_admin_type: bool | None = None,
    ) -> "HankkeutSimilarityPeerFinder":
        frame = pd.read_csv(path, dtype={"region_id": str})
        return cls(
            frame,
            default_k=default_k,
            min_similarity=min_similarity,
            same_admin_type=same_admin_type,
        )

    def find_peers(
        self, target_region_id: str, *, k: int | None = None
    ) -> pd.DataFrame:
        peers, _ = find_peers(
            self._features,
            target_region_id,
            k=k if k is not None else self._default_k,
            min_similarity=self._min_similarity,
            same_admin_type=self._same_admin_type,
        )
        return validate(peers, PEER_COLUMNS, "peers")


def find_peers(
    features: pd.DataFrame,
    target_region_id: str,
    *,
    k: int | None = None,
    min_similarity: float | None = None,
    same_admin_type: bool | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(peer 표, feature 기여도 표)를 돌려준다.

    기여도는 '가중 제곱차'의 비중이다. 값이 클수록 그 변수 때문에 두 지역이
    멀어졌다는 뜻이므로, 유사한 이유가 아니라 '남은 차이'를 보여 준다.
    """
    k = k if k is not None else get_config().similarity.peer_k
    min_similarity = (
        min_similarity
        if min_similarity is not None
        else get_config().similarity.min_similarity
    )
    if same_admin_type is None:
        same_admin_type = get_config().similarity.same_administrative_type

    features = normalize_feature_schema(features)
    columns = available_features(features)
    if not columns:
        raise ValueError("사용할 수 있는 유사성 feature가 없습니다.")

    scaled, _ = standardize(features, columns)
    # 결측으로 빠진 변수가 있으면 그 요인의 몫을 다른 요인으로 넘기지 않고
    # 같은 요인 안의 사용 가능한 변수끼리 다시 나눈다.
    weights = feature_weights(columns).reindex(columns).fillna(0.0)
    weights = weights / weights.sum()

    frame = features[["region_id", "province_name", "region_name", "admin_type"]].copy()
    if target_region_id not in set(frame["region_id"]):
        raise LookupError(f"{target_region_id} 를 찾을 수 없습니다.")

    target_position = frame.index[frame["region_id"] == target_region_id][0]
    target_vector = scaled.loc[target_position].to_numpy(dtype=float)

    matrix = scaled.to_numpy(dtype=float)
    difference = matrix - target_vector
    valid = ~np.isnan(difference)
    weighted_sq = np.where(valid, difference**2, 0.0) * weights.to_numpy()
    used_weight = valid * weights.to_numpy()
    used_weight_sum = used_weight.sum(axis=1)
    distance = np.full(len(frame), np.inf)
    computable = used_weight_sum > 0
    distance[computable] = np.sqrt(
        weighted_sq[computable].sum(axis=1) / used_weight_sum[computable]
    )

    frame["distance"] = distance
    frame["feature_weight_used"] = used_weight_sum
    frame["missing_feature_count"] = len(columns) - valid.sum(axis=1)
    # 거리 0 -> 유사도 1. 표준화된 가중거리라 지수 감쇠가 직관적이다.
    frame["similarity"] = np.exp(-distance)

    candidates = frame[frame["region_id"] != target_region_id]
    if same_admin_type:
        target_type = frame.loc[target_position, "admin_type"]
        filtered = candidates[candidates["admin_type"] == target_type]
        # 같은 유형이 너무 적으면(예: 특별자치시) 필터를 포기한다.
        if len(filtered) >= k:
            candidates = filtered

    candidates = candidates[candidates["similarity"] >= min_similarity]
    peers = (
        candidates.sort_values(
            ["similarity", "distance", "region_id"],
            ascending=[False, True, True],
        )
        .head(k)
        .reset_index(drop=True)
    )
    peers.insert(0, "rank", range(1, len(peers) + 1))
    extra_columns = [c for c in peers.columns if c not in PEER_COLUMNS]
    peers = peers[[*PEER_COLUMNS, *extra_columns]]
    peers = validate(peers, PEER_COLUMNS, "peers")

    contribution = _contribution_frame(
        scaled, weights, columns, target_position, peers, features
    )
    return peers, contribution


def _contribution_frame(
    scaled: pd.DataFrame,
    weights: pd.Series,
    columns: list[str],
    target_position: int,
    peers: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    """peer별로 어떤 변수가 차이를 만들었는지."""
    target_vector = scaled.loc[target_position].to_numpy()
    lookup = features.reset_index().set_index("region_id")["index"]

    rows = []
    for peer in peers.itertuples():
        position = lookup[peer.region_id]
        difference = scaled.loc[position].to_numpy(dtype=float) - target_vector
        valid = ~np.isnan(difference)
        weighted_sq = np.where(valid, difference**2, 0.0) * weights.to_numpy()
        total = weighted_sq.sum()
        for column, value in zip(columns, weighted_sq, strict=True):
            rows.append(
                {
                    "region_id": peer.region_id,
                    "region_name": peer.region_name,
                    "feature": column,
                    "difference_share": value / total if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def compare_values(
    features: pd.DataFrame, target_region_id: str, peer_ids: list[str]
) -> pd.DataFrame:
    """입력 지역과 peer들의 원본 feature 값 비교표."""
    columns = available_features(features)
    subset = features[features["region_id"].isin([target_region_id, *peer_ids])]
    display = subset[["region_name", *columns]].set_index("region_name")
    return display.T
