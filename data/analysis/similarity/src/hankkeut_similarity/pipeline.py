"""과제 1 PeerFinder용 데이터셋 조립."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .config import (
    PROCESSED_DIR,
    env_allows_mock_structural,
    get_config,
    sgis_credentials,
)
from .peers import compare_values, find_peers
from .provenance import Provenance, SourceRecord, SourceType
from .regions import build_region_master, load_resources
from .similarity import available_features, build_similarity_features
from .sources.sgis import SgisClient
from .sources.structural import (
    MockStructuralProvider,
    SgisStructuralProvider,
    load_coastal_flags,
    region_centroids,
)


@dataclass
class PeerAnalysisResult:
    target: pd.Series
    peers: pd.DataFrame
    contribution: pd.DataFrame
    feature_comparison: pd.DataFrame
    provenance: Provenance
    features: pd.DataFrame = field(repr=False)


@dataclass
class SimilarityDataset:
    """PeerFinder가 쓰는 지역 마스터와 구조 feature 표."""

    regions: pd.DataFrame
    resources: pd.DataFrame
    features: pd.DataFrame
    provenance: Provenance


def _structural_provider():
    credentials = sgis_credentials()
    if credentials:
        return SgisStructuralProvider(SgisClient(*credentials))
    if get_config().similarity.allow_mock_structural or env_allows_mock_structural():
        return MockStructuralProvider()
    raise RuntimeError(
        "SGIS_CONSUMER_KEY/SGIS_CONSUMER_SECRET이 없어 구조 변수 실데이터를 "
        "불러올 수 없습니다. 개발용 합성값으로만 실행하려면 "
        "--allow-mock-structural 또는 TOURGAP_ALLOW_MOCK_STRUCTURAL=1을 "
        "명시하세요. 정책 판단에는 mock 결과를 쓰면 안 됩니다."
    )


def _static_climate_features(path: Path | None = None) -> pd.DataFrame | None:
    source = path or PROCESSED_DIR / "kma_climate_normals_by_region.csv"
    if not source.exists():
        return None
    return pd.read_csv(source, dtype={"region_id": str})


def _static_terrain_features(path: Path | None = None) -> pd.DataFrame | None:
    source = path or PROCESSED_DIR / "dem_terrain_relief_by_region.csv"
    if not source.exists():
        return None
    return pd.read_csv(source, dtype={"region_id": str})


def _static_land_cover_features(path: Path | None = None) -> pd.DataFrame | None:
    source = path or PROCESSED_DIR / "land_cover_by_region.csv"
    if not source.exists():
        return None
    return pd.read_csv(source, dtype={"region_id": str})


def _merge_static_features(base: pd.DataFrame, static: pd.DataFrame) -> pd.DataFrame:
    """같은 컬럼이 있으면 정적 산출값을 우선해 덮어쓴다."""
    merged = base.merge(static, on="region_id", how="left", suffixes=("", "__static"))
    for column in [c for c in static.columns if c != "region_id"]:
        static_column = f"{column}__static"
        if static_column not in merged.columns:
            continue
        merged[column] = merged[static_column].combine_first(merged[column])
        merged = merged.drop(columns=[static_column])
    return merged


def load_dataset() -> SimilarityDataset:
    provenance = Provenance()

    resources = load_resources()
    regions = build_region_master(resources)
    provenance.add(
        SourceRecord(
            name="지역 마스터",
            source_type=SourceType.REAL,
            endpoint="KorService2 /areaBasedList2 lDongRegnCd·lDongSignguCd",
            reference_period="2026-08-17 수집분",
            note="KTO 실제 관광자원 lDong 5자리 코드 기준. 일반구는 모 시로 합산",
            row_count=len(regions),
        )
    )

    structural = _structural_provider().load(regions, provenance)

    centroids = region_centroids(resources)
    provenance.add(
        SourceRecord(
            name="지역 중심점·대도시 접근성",
            source_type=SourceType.PROXY,
            endpoint="KorService2 좌표 중앙값 + 대도시 직선거리",
            reference_period="2026-08-17 수집분",
            note="자원 '좌표'만 사용(개수·유형 미사용). 이동시간이 아닌 직선거리",
            row_count=len(centroids),
        )
    )

    coastal = load_coastal_flags(regions)
    provenance.add(
        SourceRecord(
            name="해안·도서 여부",
            source_type=SourceType.STATIC_REFERENCE,
            endpoint="data/reference/coastal_island.csv",
            reference_period="2026년 행정구역 기준",
            note="원천 여건. 직접 정리한 표",
            row_count=int(coastal["coastal_flag"].sum()),
        )
    )

    climate = _static_climate_features()
    if climate is not None:
        structural = _merge_static_features(structural, climate)
        provenance.add(
            SourceRecord(
                name="기후평년값",
                source_type=SourceType.PROXY,
                endpoint="data/processed/kma_climate_normals_by_region.csv",
                reference_period="1991~2020 기상청 기후평년값",
                note="관측소 평년값을 시군구 중심점 기준 가까운 3개 관측소 역거리 제곱으로 보간",
                row_count=int(climate["annual_mean_temperature"].notna().sum()),
            )
        )

    terrain = _static_terrain_features()
    if terrain is not None:
        structural = _merge_static_features(structural, terrain)
        provenance.add(
            SourceRecord(
                name="지형 기복",
                source_type=SourceType.STATIC_REFERENCE,
                endpoint="data/processed/dem_terrain_relief_by_region.csv",
                reference_period="국토지리정보원 한반도 90m DEM",
                note="시군구 경계 내 P90 고도-P10 고도. 2026년 분할 지역은 proxy",
                row_count=int(terrain["terrain_relief"].notna().sum()),
            )
        )

    land_cover = _static_land_cover_features()
    if land_cover is not None:
        structural = _merge_static_features(structural, land_cover)
        provenance.add(
            SourceRecord(
                name="토지피복",
                source_type=SourceType.STATIC_REFERENCE,
                endpoint="data/processed/land_cover_by_region.csv",
                reference_period="2024년 기준 국가토지피복통계",
                note=(
                    "산림=활엽수림+침엽수림+혼효림, "
                    "농지=논·밭·시설재배지·과수원·목장양식장·기타재배지. "
                    "일반구는 모 시 합산, 인천 2026년 분할 지역은 보정표로 면적 배분"
                ),
                row_count=int(land_cover["forest_ratio"].notna().sum()),
            )
        )

    features = build_similarity_features(regions, structural, centroids, coastal)

    return SimilarityDataset(
        regions=regions,
        resources=resources,
        features=features,
        provenance=provenance,
    )


def analyze(dataset: SimilarityDataset, target: pd.Series) -> PeerAnalysisResult:
    target_id = target["region_id"]
    peers, contribution = find_peers(dataset.features, target_id)
    peer_ids = peers["region_id"].tolist()
    comparison = compare_values(dataset.features, target_id, peer_ids)
    return PeerAnalysisResult(
        target=target,
        peers=peers,
        contribution=contribution,
        feature_comparison=comparison,
        provenance=dataset.provenance,
        features=dataset.features,
    )


def similarity_feature_names(dataset: SimilarityDataset) -> list[str]:
    return available_features(dataset.features)
