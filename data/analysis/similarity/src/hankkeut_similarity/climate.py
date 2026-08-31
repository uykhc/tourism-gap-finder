"""기상청 1991~2020 기후평년값을 시군구 feature로 변환한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PROCESSED_DIR, RAW_DIR
from .data_sources import KmaClimateNormalsSource
from .regions import build_region_master, load_resources
from .sources.structural import haversine_km, region_centroids

DEFAULT_OUTPUT = PROCESSED_DIR / "kma_climate_normals_by_region.csv"
MONTH_COLUMNS = [f"{month}월" for month in range(1, 13)]


def build_climate_features(
    regions: pd.DataFrame,
    centroids: pd.DataFrame,
    station_normals: pd.DataFrame,
    *,
    nearest_k: int = 3,
) -> pd.DataFrame:
    """관측소 평년값을 시군구 중심점 기준 역거리 제곱으로 보간한다."""
    if nearest_k <= 0:
        raise ValueError("nearest_k는 1 이상이어야 합니다.")

    stations = station_normals.dropna(
        subset=[
            "longitude",
            "latitude",
            "annual_mean_temperature",
            "annual_temperature_range",
            "annual_precipitation",
        ]
    ).copy()
    if stations.empty:
        raise ValueError("사용 가능한 기상청 관측소 평년값이 없습니다.")

    frame = regions[["region_id", "province_name", "region_name"]].merge(
        centroids, on="region_id", how="left"
    )

    rows = []
    for region in frame.itertuples():
        if pd.isna(region.centroid_lon) or pd.isna(region.centroid_lat):
            rows.append(_missing_region_record(region, "region centroid is missing"))
            continue

        distances = stations.apply(
            lambda station: haversine_km(
                float(region.centroid_lon),
                float(region.centroid_lat),
                float(station.longitude),
                float(station.latitude),
            ),
            axis=1,
        )
        nearest = stations.assign(distance_km=distances).nsmallest(
            nearest_k, "distance_km"
        )
        rows.append(_weighted_region_record(region, nearest, nearest_k=nearest_k))

    return pd.DataFrame(rows)


def load_kma_station_normals(
    *,
    monthly_path: str | Path,
    annual_path: str | Path,
    station_metadata: pd.DataFrame,
) -> pd.DataFrame:
    """기상청 월별/연별 파일과 지점 메타데이터를 관측소 feature로 합친다."""
    annual = _read_annual_normals(annual_path)
    monthly = _read_monthly_mean_temperature(monthly_path)

    monthly["annual_temperature_range"] = monthly[MONTH_COLUMNS].max(axis=1) - monthly[
        MONTH_COLUMNS
    ].min(axis=1)
    monthly = monthly[["station_id", "annual_temperature_range"]]

    stations = annual.merge(monthly, on="station_id", how="inner").merge(
        station_metadata,
        on="station_id",
        how="left",
        suffixes=("", "_metadata"),
    )
    if "station_name_metadata" in stations.columns:
        stations["station_name"] = stations["station_name"].fillna(
            stations["station_name_metadata"]
        )
        stations = stations.drop(columns=["station_name_metadata"])
    return stations


def build_and_save(
    *,
    output_path: str | Path = DEFAULT_OUTPUT,
    monthly_path: str | Path | None = None,
    annual_path: str | Path | None = None,
    nearest_k: int = 3,
    refresh_downloads: bool = False,
) -> Path:
    """공식 파일 다운로드부터 시군구별 CSV 저장까지 한 번에 수행한다."""
    source = KmaClimateNormalsSource(cache_dir=RAW_DIR / "kma")
    monthly = (
        Path(monthly_path)
        if monthly_path
        else _cached_or_download(source, "monthly", refresh=refresh_downloads)
    )
    annual = (
        Path(annual_path)
        if annual_path
        else _cached_or_download(source, "annual", refresh=refresh_downloads)
    )

    station_metadata = source.station_metadata()
    station_normals = load_kma_station_normals(
        monthly_path=monthly,
        annual_path=annual,
        station_metadata=station_metadata,
    )

    resources = load_resources()
    regions = build_region_master(resources)
    centroids = region_centroids(resources)
    features = build_climate_features(
        regions,
        centroids,
        station_normals,
        nearest_k=nearest_k,
    )
    features["annual_mean_temperature_source_type"] = "proxy"
    features["annual_temperature_range_source_type"] = "proxy"
    features["annual_precipitation_source_type"] = "proxy"
    features["climate_source_period"] = "1991-2020"
    features["climate_source_name"] = "KMA climate normals fileset"
    features["monthly_normals_file"] = monthly.name
    features["annual_normals_file"] = annual.name

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output, index=False)
    return output


def _read_annual_normals(path: str | Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=0, header=None, skiprows=4)
    frame = raw.iloc[:, [0, 1, 3, 10]].copy()
    frame.columns = [
        "station_id",
        "station_name",
        "annual_mean_temperature",
        "annual_precipitation",
    ]
    frame["station_id"] = _normalize_station_id(frame["station_id"])
    for column in ["annual_mean_temperature", "annual_precipitation"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["annual_mean_temperature", "annual_precipitation"])


def _read_monthly_mean_temperature(path: str | Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="3.평균기온", header=None, skiprows=5)
    frame = raw.iloc[:, :14].copy()
    frame.columns = ["station_id", "station_name", *MONTH_COLUMNS]
    frame["station_id"] = _normalize_station_id(frame["station_id"])
    for column in MONTH_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=MONTH_COLUMNS, how="all")


def _weighted_region_record(
    region, nearest: pd.DataFrame, *, nearest_k: int
) -> dict[str, object]:
    distances = nearest["distance_km"].astype(float).to_numpy()
    # 같은 지점 위에 중심점이 놓이는 경우 0거리 관측소 하나에 전체 가중치를 둔다.
    if np.any(distances == 0):
        weights = np.where(distances == 0, 1.0, 0.0)
        weights = weights / weights.sum()
    else:
        weights = 1 / np.square(distances)
        weights = weights / weights.sum()

    record = {
        "region_id": region.region_id,
        "annual_mean_temperature": _weighted_average(
            nearest["annual_mean_temperature"], weights
        ),
        "annual_temperature_range": _weighted_average(
            nearest["annual_temperature_range"], weights
        ),
        "annual_precipitation": _weighted_average(
            nearest["annual_precipitation"], weights
        ),
        "climate_station_ids": json.dumps(
            nearest["station_id"].astype(str).tolist(), ensure_ascii=False
        ),
        "climate_station_names": json.dumps(
            nearest["station_name"].astype(str).tolist(), ensure_ascii=False
        ),
        "climate_station_distances_km": json.dumps(
            [round(float(value), 3) for value in nearest["distance_km"]],
            ensure_ascii=False,
        ),
        "climate_station_weights": json.dumps(
            [round(float(value), 6) for value in weights],
            ensure_ascii=False,
        ),
        "climate_interpolation_method": (
            f"nearest_{nearest_k}_inverse_distance_squared"
        ),
    }
    return record


def _missing_region_record(region, reason: str) -> dict[str, object]:
    return {
        "region_id": region.region_id,
        "annual_mean_temperature": np.nan,
        "annual_temperature_range": np.nan,
        "annual_precipitation": np.nan,
        "annual_mean_temperature_missing_reason": reason,
        "annual_temperature_range_missing_reason": reason,
        "annual_precipitation_missing_reason": reason,
        "climate_interpolation_method": "",
    }


def _weighted_average(values: pd.Series, weights: np.ndarray) -> float:
    return round(float(np.sum(values.astype(float).to_numpy() * weights)), 3)


def _normalize_station_id(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").astype("Int64").astype(str)


def _cached_or_download(
    source: KmaClimateNormalsSource, period: str, *, refresh: bool
) -> Path:
    target = source.cache_dir / f"kma_climate_normals_1991_2020_{period}.xlsx"
    if target.exists() and not refresh:
        return target
    return source.download(period)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="기상청 1991~2020 기후평년값을 시군구별 정적 feature로 저장"
    )
    parser.add_argument("--monthly", help="이미 받은 월별 기후평년값 xlsx 경로")
    parser.add_argument("--annual", help="이미 받은 연별 기후평년값 xlsx 경로")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="저장할 CSV 경로")
    parser.add_argument("--nearest-k", type=int, default=3, help="사용 관측소 수")
    parser.add_argument(
        "--refresh-downloads",
        action="store_true",
        help="기존 raw 파일이 있어도 기상청 공식 파일셋을 다시 다운로드",
    )
    args = parser.parse_args(argv)

    path = build_and_save(
        output_path=args.output,
        monthly_path=args.monthly,
        annual_path=args.annual,
        nearest_k=args.nearest_k,
        refresh_downloads=args.refresh_downloads,
    )
    print(f"기후 feature 저장: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
