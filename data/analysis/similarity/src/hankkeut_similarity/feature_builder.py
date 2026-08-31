"""과제 1 구조 특성 테이블 생성과 검증.

최종 유사도 변수는 config.SIMILARITY_FEATURES의 17개로 고정한다.
이 모듈은 원자료를 지역 단위로 조인하고, 유사도 계산 직전 입력 계약을
검증한다. 결측은 임의로 0으로 채우지 않는다.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import LOG_TRANSFORM_COLUMNS, SIMILARITY_FEATURES

FEATURE_COLUMNS = list(SIMILARITY_FEATURES)
RATIO_COLUMNS = [
    "urbanization_ratio",
    "island_ratio",
    "forest_ratio",
    "farmland_ratio",
    "manufacturing_worker_ratio",
    "construction_logistics_worker_ratio",
    "knowledge_public_service_worker_ratio",
]
SOURCE_TYPES = {"real", "proxy", "static_reference", "mock"}

LEGACY_ALIASES = {
    "population": "total_population",
    "density": "population_density",
    "coastal_flag": "coastal_dummy",
    "island_flag": "island_ratio",
}


def build_feature_table(
    regions: pd.DataFrame,
    *,
    structural: pd.DataFrame,
    geography: pd.DataFrame | None = None,
    climate: pd.DataFrame | None = None,
    industry: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """지역 마스터와 영역별 원자료를 17개 feature 표로 조인한다."""
    frame = regions[["region_id", "province_name", "region_name", "admin_type"]].copy()
    for source in (structural, geography, climate, industry):
        if source is None or source.empty:
            continue
        frame = frame.merge(source, on="region_id", how="left")

    frame = normalize_feature_schema(frame)
    validate_feature_table(frame, require_all_features=False)
    return frame


def normalize_feature_schema(frame: pd.DataFrame) -> pd.DataFrame:
    """기존 MVP 컬럼명을 확정된 17개 변수명으로 맞춘다."""
    result = frame.copy()
    for column in FEATURE_COLUMNS:
        left = f"{column}_x"
        right = f"{column}_y"
        if column not in result.columns and (
            left in result.columns or right in result.columns
        ):
            if left in result.columns and right in result.columns:
                result[column] = result[right].where(
                    result[right].notna(), result[left]
                )
            elif right in result.columns:
                result[column] = result[right]
            else:
                result[column] = result[left]

    for old, new in LEGACY_ALIASES.items():
        if old in result.columns and new not in result.columns:
            result[new] = result[old]

    if (
        "total_population" in result.columns
        and "area_km2" in result.columns
        and "population_density" not in result.columns
    ):
        result["population_density"] = result["total_population"] / result["area_km2"]

    if "coastal_dummy" in result.columns:
        result["coastal_dummy"] = pd.to_numeric(
            result["coastal_dummy"], errors="coerce"
        )
    if "island_ratio" in result.columns:
        result["island_ratio"] = pd.to_numeric(result["island_ratio"], errors="coerce")
    return result


def validate_feature_table(
    frame: pd.DataFrame, *, require_all_features: bool = True
) -> pd.DataFrame:
    """feature 테이블 입력 계약을 검증한다."""
    if "region_id" not in frame.columns:
        raise ValueError("feature table에 region_id 컬럼이 없습니다.")

    region_ids = frame["region_id"].astype(str)
    invalid_ids = region_ids[~region_ids.str.fullmatch(r"\d{5}")]
    if len(invalid_ids):
        sample = invalid_ids.head(5).tolist()
        raise ValueError(f"region_id는 5자리 문자열이어야 합니다: {sample}")
    if region_ids.duplicated().any():
        duplicated = region_ids[region_ids.duplicated()].head(5).tolist()
        raise ValueError(f"지역당 한 행이어야 합니다. 중복: {duplicated}")

    missing_columns = [c for c in FEATURE_COLUMNS if c not in frame.columns]
    if require_all_features and missing_columns:
        raise ValueError("확정된 유사도 변수 17개가 모두 필요합니다. " f"누락: {missing_columns}")

    for column in RATIO_COLUMNS:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            invalid = values.notna() & ~values.between(0, 1)
            if invalid.any():
                raise ValueError(f"{column} 값은 0~1 범위여야 합니다.")

    if "coastal_dummy" in frame.columns:
        values = pd.to_numeric(frame["coastal_dummy"], errors="coerce")
        invalid = values.notna() & ~values.isin([0, 1])
        if invalid.any():
            raise ValueError("coastal_dummy 값은 0 또는 1이어야 합니다.")

    if {
        "total_population",
        "area_km2",
        "population_density",
    } <= set(frame.columns):
        expected = frame["total_population"] / frame["area_km2"]
        actual = pd.to_numeric(frame["population_density"], errors="coerce")
        comparable = expected.notna() & actual.notna() & (expected != 0)
        relative_error = ((actual - expected).abs() / expected).where(comparable)
        if (relative_error > 0.02).any():
            raise ValueError("population_density가 total_population/area_km2와 다릅니다.")

    for feature in FEATURE_COLUMNS:
        source_type = f"{feature}_source_type"
        if source_type not in frame.columns:
            continue
        values = set(frame[source_type].dropna().astype(str))
        unknown = values - SOURCE_TYPES
        if unknown:
            raise ValueError(f"{source_type}에 알 수 없는 출처 유형이 있습니다: {unknown}")

    return frame


def missing_feature_report(frame: pd.DataFrame) -> pd.DataFrame:
    """지역별 feature 누락 사유를 길게 펼친 표로 만든다."""
    rows = []
    for row in normalize_feature_schema(frame).itertuples(index=False):
        region_id = getattr(row, "region_id")
        for feature in FEATURE_COLUMNS:
            value = getattr(row, feature, np.nan)
            if pd.notna(value):
                continue
            reason_column = f"{feature}_missing_reason"
            reason = getattr(row, reason_column, "")
            rows.append(
                {
                    "region_id": region_id,
                    "feature": feature,
                    "missing_reason": reason or "source value is missing",
                }
            )
    return pd.DataFrame(rows)


def preprocess_similarity_values(
    frame: pd.DataFrame,
    columns: list[str],
    *,
    log_columns: tuple[str, ...] = LOG_TRANSFORM_COLUMNS,
) -> pd.DataFrame:
    """로그 변환 대상만 log1p 후 숫자 행렬을 반환한다."""
    values = frame[columns].apply(pd.to_numeric, errors="coerce").astype(float)
    for column in set(columns) & set(log_columns):
        negative = values[column].notna() & (values[column] < 0)
        if negative.any():
            raise ValueError(f"{column}에는 log1p를 적용할 수 없는 음수가 있습니다.")
        values[column] = np.log1p(values[column])
    return values
