"""전국 90m DEM에서 시군구별 지형 기복을 계산한다."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PROCESSED_DIR, PROJECT_ROOT, RAW_DIR, sgis_credentials
from .regions import build_region_master, load_resources
from .sources.sgis import SgisClient
from .sources.structural import PROVINCE_ALIASES, SGIS_MAP_PATH, canonical_province

DEFAULT_DEM = RAW_DIR / "dem" / "한반도90m_GRS80.img"
DEFAULT_OUTPUT = PROCESSED_DIR / "dem_terrain_relief_by_region.csv"


def build_terrain_features(
    dem_path: str | Path,
    regions: pd.DataFrame,
    client: SgisClient,
    *,
    boundary_year: str = "2020",
) -> pd.DataFrame:
    """SGIS 경계 안의 P90 고도-P10 고도를 지형 기복으로 계산한다."""
    try:
        import rasterio
        from rasterio.mask import mask
        from rasterio.warp import transform_geom
    except ImportError as exc:
        raise RuntimeError(
            "DEM 전처리에는 rasterio가 필요합니다. " "pip install -e '.[geospatial]' 후 다시 실행하세요."
        ) from exc

    groups: dict[tuple[str, str], list[dict]] = {}
    for province in client.fetch_population(year=boundary_year, low_search="1"):
        payload = client.fetch_boundary(
            year=boundary_year,
            adm_cd=str(province.get("adm_cd", "")),
            low_search="1",
        )
        for feature in payload.get("features", []):
            properties = feature.get("properties") or {}
            tokens = str(properties.get("adm_nm", "")).split()
            if len(tokens) < 2 or not feature.get("geometry"):
                continue
            key = (canonical_province(tokens[0]), tokens[1])
            groups.setdefault(key, []).append(feature["geometry"])

    rows: list[dict[str, object]] = []
    with rasterio.open(dem_path) as dataset:
        for (province_key, municipality), geometries in groups.items():
            projected = [
                transform_geom("EPSG:5179", dataset.crs, geometry)
                for geometry in geometries
            ]
            values, _ = mask(dataset, projected, crop=True, filled=False, indexes=1)
            pixels = values.compressed().astype(float)
            pixels = pixels[np.isfinite(pixels)]
            if len(pixels):
                p10, p90 = np.percentile(pixels, [10, 90])
                relief = p90 - p10
            else:
                p10 = p90 = relief = float("nan")
            rows.append(
                {
                    "_province_key": province_key,
                    "sgis_municipality": municipality,
                    "elevation_p10_m": p10,
                    "elevation_p90_m": p90,
                    "terrain_relief": relief,
                    "dem_pixel_count": len(pixels),
                }
            )

    by_name = pd.DataFrame(rows).set_index(["_province_key", "sgis_municipality"])
    municipality_counts = pd.Series(
        [municipality for _, municipality in by_name.index]
    ).value_counts()
    overrides = (
        pd.read_csv(SGIS_MAP_PATH, dtype={"region_id": str})
        if SGIS_MAP_PATH.exists()
        else pd.DataFrame()
    )
    override_ids = set(overrides.get("region_id", []))
    result: list[dict[str, object]] = []
    for region in regions.itertuples():
        if region.region_id in override_ids:
            mapping = overrides[overrides["region_id"] == region.region_id]
            matches = []
            for item in mapping.itertuples():
                key = (canonical_province(item.sgis_province), item.sgis_municipality)
                if key in by_name.index:
                    matches.append((float(item.weight), by_name.loc[key]))
            result.append(_weighted_override_record(region.region_id, matches))
            continue

        record = None
        for province in PROVINCE_ALIASES.get(
            region.province_name, [region.province_name]
        ):
            key = (canonical_province(province), region.region_name)
            if key in by_name.index:
                record = by_name.loc[key]
                break
        # 군위군처럼 기준연도 뒤에 소속 시도가 바뀐 지역은, 전국에서 지역명이
        # 유일할 때에만 이전 시도의 동일 경계를 안전하게 재사용한다.
        if record is None and municipality_counts.get(region.region_name, 0) == 1:
            record = by_name.xs(region.region_name, level="sgis_municipality").iloc[0]
        result.append(_direct_record(region.region_id, record))
    return pd.DataFrame(result)


def _direct_record(region_id: str, record) -> dict[str, object]:
    if record is None:
        return {
            "region_id": region_id,
            "terrain_relief": float("nan"),
            "terrain_relief_source_type": "static_reference",
            "terrain_relief_missing_reason": "SGIS boundary or DEM pixels missing",
        }
    return {
        "region_id": region_id,
        "elevation_p10_m": float(record["elevation_p10_m"]),
        "elevation_p90_m": float(record["elevation_p90_m"]),
        "terrain_relief": float(record["terrain_relief"]),
        "dem_pixel_count": int(record["dem_pixel_count"]),
        "terrain_relief_source_type": "static_reference",
        "terrain_relief_missing_reason": "",
    }


def _weighted_override_record(region_id: str, matches: list[tuple[float, object]]):
    if not matches:
        return _direct_record(region_id, None)
    total_weight = sum(weight for weight, _ in matches)

    def weighted(column: str) -> float:
        return (
            sum(weight * float(record[column]) for weight, record in matches)
            / total_weight
        )

    return {
        "region_id": region_id,
        "elevation_p10_m": weighted("elevation_p10_m"),
        "elevation_p90_m": weighted("elevation_p90_m"),
        "terrain_relief": weighted("terrain_relief"),
        "dem_pixel_count": int(
            sum(weight * float(record["dem_pixel_count"]) for weight, record in matches)
        ),
        "terrain_relief_source_type": "proxy",
        "terrain_relief_missing_reason": "2026 administrative split estimated from prior SGIS boundaries",
    }


def build_and_save(dem_path: str | Path = DEFAULT_DEM) -> pd.DataFrame:
    credentials = sgis_credentials()
    if not credentials:
        raise RuntimeError("SGIS_CONSUMER_KEY/SGIS_CONSUMER_SECRET이 필요합니다.")
    regions = build_region_master(load_resources())
    result = build_terrain_features(dem_path, regions, SgisClient(*credentials))
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(DEFAULT_OUTPUT, index=False)
    return result


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    parser = argparse.ArgumentParser(description="전국 90m DEM 지형 기복 생성")
    parser.add_argument("--dem", type=Path, default=DEFAULT_DEM)
    args = parser.parse_args(argv)
    load_dotenv(PROJECT_ROOT / ".env")
    result = build_and_save(args.dem)
    print(f"{DEFAULT_OUTPUT}: {len(result)}개 지역")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
