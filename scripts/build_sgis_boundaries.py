"""Build the nationwide Kakao collection boundary from SGIS boundaries.

SGIS publishes municipality geometry in EPSG:5179 while the Kakao collector
requires WGS84.  The source also follows an older administrative geography, so
this producer refuses to invent polygons for split municipalities.  A partial
override GeoJSON may supply official replacement polygons and their TourAPI
codes for those regions.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from pyproj import Transformer

from apps.api.app.services import regions
from hankkeut_similarity.config import (
    REFERENCE_DIR,
    load_project_environment,
    sgis_credentials,
)
from hankkeut_similarity.sources.sgis import SgisClient
from hankkeut_similarity.sources.structural import canonical_province

DEFAULT_POPULATION_YEAR = "2020"
DEFAULT_BOUNDARY_YEAR = "2025"
DEFAULT_MAP_PATH = REFERENCE_DIR / "sgis_region_map.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--population-year", default=DEFAULT_POPULATION_YEAR)
    parser.add_argument("--boundary-year", default=DEFAULT_BOUNDARY_YEAR)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument(
        "--override-boundaries",
        type=Path,
        help=(
            "Partial WGS84 FeatureCollection for administrative splits that SGIS "
            "does not publish. Each feature must include region_id and, when the "
            "repository has no TourAPI mapping, area_code and sigungu_code."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_project_environment()
    credentials = sgis_credentials()
    if credentials is None:
        raise RuntimeError("SGIS_CONSUMER_KEY/SGIS_CONSUMER_SECRET이 필요합니다.")

    cache_dir = args.cache_dir
    if cache_dir is None:
        configured = os.getenv("HANKKEUT_CACHE_ROOT", "").strip()
        cache_dir = Path(configured) / "sgis-boundaries" if configured else None
    client = SgisClient(*credentials, cache_dir=cache_dir)
    raw_features = collect_boundaries(
        client,
        population_year=args.population_year,
        boundary_year=args.boundary_year,
    )
    overrides = _load_feature_collection(args.override_boundaries)
    payload = normalize_boundaries(
        raw_features,
        region_rows=regions.all_regions(),
        mapping_rows=_load_mapping_rows(DEFAULT_MAP_PATH),
        override_features=overrides,
        population_year=args.population_year,
        boundary_year=args.boundary_year,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"SGIS 전국 경계 저장: {args.output} ({len(payload['features'])}개 지역)")
    return 0


def collect_boundaries(
    client: SgisClient, *, population_year: str, boundary_year: str
) -> list[dict[str, Any]]:
    """Fetch every province once and return its municipality features."""
    features: list[dict[str, Any]] = []
    provinces = client.fetch_population(year=population_year, low_search="1")
    for province in provinces:
        province_code = str(province.get("adm_cd") or "").strip()
        if not province_code:
            raise ValueError("SGIS 시도 응답에 adm_cd가 없습니다.")
        payload = client.fetch_boundary(
            year=boundary_year,
            adm_cd=province_code,
            low_search="1",
        )
        province_features = payload.get("features")
        if not isinstance(province_features, list) or not province_features:
            raise ValueError(
                f"SGIS 경계가 비어 있습니다: adm_cd={province_code}, year={boundary_year}"
            )
        features.extend(item for item in province_features if isinstance(item, dict))
    return features


def normalize_boundaries(
    source_features: Iterable[dict[str, Any]],
    *,
    region_rows: list[dict[str, Any]],
    mapping_rows: list[dict[str, str]],
    override_features: list[dict[str, Any]] | None = None,
    population_year: str = DEFAULT_POPULATION_YEAR,
    boundary_year: str = DEFAULT_BOUNDARY_YEAR,
) -> dict[str, Any]:
    """Map historical SGIS names to the current region master and emit WGS84."""
    by_id = {str(row["region_id"]): row for row in region_rows}
    direct = {
        (canonical_province(str(row["province_name"])), str(row["region_name"])): str(
            row["region_id"]
        )
        for row in region_rows
    }
    name_counts = Counter(str(row["region_name"]) for row in region_rows)
    unique_names = {
        str(row["region_name"]): str(row["region_id"])
        for row in region_rows
        if name_counts[str(row["region_name"])] == 1
    }
    safe_mappings = _safe_mapping_index(mapping_rows)
    polygons_by_id: dict[str, list[Any]] = defaultdict(list)
    unresolved_sources: list[str] = []
    transformer = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

    for feature in source_features:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("SGIS 경계 feature에 properties 또는 geometry가 없습니다.")
        tokens = str(properties.get("adm_nm") or "").strip().split()
        if len(tokens) < 2:
            raise ValueError(f"SGIS adm_nm을 해석할 수 없습니다: {properties.get('adm_nm')!r}")
        source_key = (canonical_province(tokens[0]), tokens[1])
        region_id = direct.get(source_key)
        if region_id is None:
            region_id = unique_names.get(tokens[1])
        if region_id is None:
            region_id = safe_mappings.get(source_key)
        if region_id is None:
            unresolved_sources.append(" ".join(tokens))
            continue
        polygons_by_id[region_id].extend(_as_wgs84_polygons(geometry, transformer))

    output_by_id: dict[str, dict[str, Any]] = {}
    for region_id, polygons in polygons_by_id.items():
        output_by_id[region_id] = _output_feature(
            by_id[region_id],
            {"type": "MultiPolygon", "coordinates": polygons},
            override_properties=None,
        )

    for feature in override_features or []:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("override 경계 feature에 properties 또는 geometry가 없습니다.")
        region_id = str(properties.get("region_id") or "").strip()
        if region_id not in by_id:
            raise ValueError(f"override 경계의 region_id가 지역 마스터에 없습니다: {region_id}")
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(
                f"override 경계는 Polygon 또는 MultiPolygon이어야 합니다: {region_id}"
            )
        _assert_wgs84(geometry.get("coordinates"), region_id=region_id)
        output_by_id[region_id] = _output_feature(
            by_id[region_id], geometry, override_properties=properties
        )

    expected = set(by_id)
    found = set(output_by_id)
    missing = sorted(expected - found)
    extra = sorted(found - expected)
    if missing or extra:
        unresolved = sorted(set(unresolved_sources))
        raise ValueError(
            "전국 경계를 완성할 수 없습니다. "
            f"missing_region_ids={missing}, extra_region_ids={extra}, "
            f"unresolved_sgis_names={unresolved}. "
            "행정구역 분할 지역은 공식 WGS84 override 경계와 TourAPI 코드를 제공해야 합니다."
        )

    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": "SGIS OpenAPI3 /boundary/hadmarea.geojson",
            "source_crs": "EPSG:5179",
            "output_crs": "EPSG:4326",
            "population_year": population_year,
            "boundary_year": boundary_year,
            "region_count": len(output_by_id),
        },
        "features": [output_by_id[region_id] for region_id in sorted(output_by_id)],
    }


def _safe_mapping_index(rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    by_target: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_target[row["region_id"]].append(row)
    safe: dict[tuple[str, str], str] = {}
    for region_id, target_rows in by_target.items():
        if len(target_rows) != 1:
            continue
        row = target_rows[0]
        try:
            weight = float(row.get("weight") or 0)
        except ValueError:
            continue
        if weight != 1.0:
            continue
        safe[(canonical_province(row["sgis_province"]), row["sgis_municipality"])] = region_id
    return safe


def _output_feature(
    region: dict[str, Any],
    geometry: dict[str, Any],
    *,
    override_properties: dict[str, Any] | None,
) -> dict[str, Any]:
    region_id = str(region["region_id"])
    code = regions.tour_api_code(region_id)
    if code is None:
        supplied = override_properties or {}
        area_code = str(supplied.get("area_code") or "").strip()
        sigungu_code = str(supplied.get("sigungu_code") or "").strip()
        if not area_code or not sigungu_code:
            raise ValueError(
                f"TourAPI 코드가 없는 override 경계입니다: {region_id}. "
                "properties.area_code와 properties.sigungu_code가 필요합니다."
            )
    else:
        area_code, sigungu_code = code
    return {
        "type": "Feature",
        "properties": {
            "region_id": region_id,
            "area_code": area_code,
            "sigungu_code": sigungu_code,
            "province_name": str(region["province_name"]),
            "region_name": str(region["region_name"]),
        },
        "geometry": geometry,
    }


def _as_wgs84_polygons(
    geometry: dict[str, Any], transformer: Transformer
) -> list[Any]:
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        polygons = [coordinates]
    elif geometry_type == "MultiPolygon":
        polygons = coordinates
    else:
        raise ValueError(f"지원하지 않는 SGIS geometry type입니다: {geometry_type}")
    if not isinstance(polygons, list):
        raise ValueError("SGIS geometry coordinates가 배열이 아닙니다.")
    return [_transform_nested(polygon, transformer) for polygon in polygons]


def _transform_nested(value: Any, transformer: Transformer) -> Any:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        longitude, latitude = transformer.transform(float(value[0]), float(value[1]))
        return [round(longitude, 7), round(latitude, 7)]
    if not isinstance(value, list):
        raise ValueError("SGIS geometry 좌표 형식이 올바르지 않습니다.")
    return [_transform_nested(item, transformer) for item in value]


def _assert_wgs84(value: Any, *, region_id: str) -> None:
    if not isinstance(value, list) or not value:
        raise ValueError(f"override 경계 좌표가 비어 있습니다: {region_id}")
    if (
        len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        longitude, latitude = float(value[0]), float(value[1])
        if not 124.0 <= longitude <= 132.0 or not 32.0 <= latitude <= 39.5:
            raise ValueError(f"override 경계가 WGS84 대한민국 범위를 벗어납니다: {region_id}")
        return
    for item in value:
        _assert_wgs84(item, region_id=region_id)


def _load_mapping_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_feature_collection(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    features = payload.get("features") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("type") != "FeatureCollection"
        or not isinstance(features, list)
    ):
        raise ValueError("override 경계는 GeoJSON FeatureCollection이어야 합니다.")
    if any(not isinstance(item, dict) for item in features):
        raise ValueError("override 경계의 모든 feature는 객체여야 합니다.")
    return list(features)


if __name__ == "__main__":
    raise SystemExit(main())
