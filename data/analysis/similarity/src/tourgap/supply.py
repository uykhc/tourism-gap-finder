"""관광 콘텐츠 공급 집계 = 공백 분석 전용.

여기서 만든 값은 유사성이나 성과 계산에 절대 들어가지 않는다(원칙 1).

분류 축은 TourAPI 신분류체계 대분류(lclsSystm1)를 쓴다. contentTypeId
8종보다 관광 콘텐츠의 성격을 잘 나눈다. 특히 '체험관광(EX)'과
'문화관광(VE)'이 분리되어 있어 정책 언어에 가깝다.
"""

from __future__ import annotations

import pandas as pd

from .config import (
    CONTEXT_CATEGORIES,
    EXCLUDED_CATEGORIES,
    GAP_CATEGORIES,
    LCLS1_NAMES,
    get_config,
)
from .provenance import Provenance, SourceRecord, SourceType

SUPPLY_METRICS = ["raw_count", "share", "per_10k_pop", "per_100km2"]


def build_supply(
    resources: pd.DataFrame,
    structural: pd.DataFrame,
    provenance: Provenance,
    *,
    level: str = "lcls1",
) -> pd.DataFrame:
    """지역 × 카테고리 공급 지표.

    level="lcls1" 이면 대분류, "lcls2" 면 중분류로 집계한다.
    share는 '공백 랭킹 대상 카테고리 합계' 대비 비중이다. 원천자원(NA/HS)을
    분모에 넣으면 자연이 풍부한 지역의 다른 비중이 전부 눌려 버린다.
    """
    column = "lcls1" if level == "lcls1" else "lcls2"
    valid = resources[
        (resources["region_id"] != "")
        & (resources[column] != "")
        & (~resources["lcls1"].isin(EXCLUDED_CATEGORIES))
    ]

    counts = (
        valid.groupby(["region_id", column])
        .size()
        .reset_index(name="raw_count")
        .rename(columns={column: "category"})
    )

    # 모든 지역 × 모든 카테고리 조합을 채워 '없음'을 0으로 명시한다.
    # 이 과정을 건너뛰면 해당 카테고리가 아예 없는 지역이 결측으로 남아
    # benchmark 중앙값과 일관성 계산에서 조용히 빠진다.
    if level == "lcls1":
        categories = [*GAP_CATEGORIES, *CONTEXT_CATEGORIES]
    else:
        categories = sorted(counts["category"].unique())
    index = pd.MultiIndex.from_product(
        [structural["region_id"].unique(), categories],
        names=["region_id", "category"],
    )
    counts = (
        counts.set_index(["region_id", "category"])
        .reindex(index, fill_value=0)
        .reset_index()
    )

    # share의 분모는 '공백 랭킹 대상 카테고리 합계'다. 원천자원(NA/HS)을
    # 분모에 넣으면 자연·역사가 풍부한 지역의 다른 비중이 전부 눌린다.
    # 중분류는 코드 앞부분이 대분류이므로(EX03 -> EX) 그것으로 판정한다.
    if level == "lcls1":
        in_gap_scope = counts["category"].isin(GAP_CATEGORIES)
    else:
        in_gap_scope = counts["category"].str[:2].isin(GAP_CATEGORIES)

    gap_totals = (
        counts[in_gap_scope].groupby("region_id")["raw_count"].sum().rename("gap_total")
    )
    counts = counts.merge(gap_totals, on="region_id", how="left")
    counts["share"] = counts["raw_count"] / counts["gap_total"].replace(0, pd.NA)

    sizes = structural[["region_id", "area_km2"]].copy()
    if "population" in structural.columns:
        sizes["population"] = structural["population"]
    else:
        sizes["population"] = structural["total_population"]
    counts = counts.merge(sizes, on="region_id", how="left")
    counts["per_10k_pop"] = counts["raw_count"] / (counts["population"] / 10_000)
    counts["per_100km2"] = counts["raw_count"] / (counts["area_km2"] / 100)
    counts["category_name"] = counts["category"].map(lambda c: LCLS1_NAMES.get(c, c))

    if level == "lcls1":
        provenance.add(
            SourceRecord(
                name="관광 콘텐츠 공급",
                source_type=SourceType.REAL,
                endpoint="KorService2 /areaBasedList2 (lclsSystm1)",
                reference_period="2026-08-17 수집분",
                note="전국 48,858건. 등록 기준이므로 실제 공급과 다를 수 있음",
                row_count=int(len(valid)),
            )
        )
    return counts.drop(columns=["population", "area_km2"])


def registration_quality(resources: pd.DataFrame) -> pd.DataFrame:
    """지역별 등록 활성도.

    TourAPI 등록 건수는 실제 관광 콘텐츠 양이 아니라 지자체의 등록 성실도를
    함께 반영한다. 공백 해석을 오도할 수 있으므로, 표본이 적거나 갱신이
    멈춘 지역은 리포트에서 경고를 띄우기 위해 이 지표를 만든다.
    """
    valid = resources[resources["region_id"] != ""].copy()
    modified_year = pd.to_numeric(valid["modified_time"].str[:4], errors="coerce")
    current_year = 2026
    valid["is_fresh"] = modified_year >= (
        current_year - get_config().quality.stale_years
    )

    frame = (
        valid.groupby("region_id")
        .agg(
            total_resources=("content_id", "size"),
            fresh_ratio=("is_fresh", "mean"),
        )
        .reset_index()
    )
    frame["low_sample"] = (
        frame["total_resources"] < get_config().quality.min_total_resources
    )
    frame["stale"] = frame["fresh_ratio"] < get_config().quality.min_fresh_ratio
    return frame


def pivot_metric(supply: pd.DataFrame, metric: str) -> pd.DataFrame:
    """지역 × 카테고리 행렬."""
    return supply.pivot_table(
        index="region_id", columns="category", values=metric, aggfunc="first"
    )
