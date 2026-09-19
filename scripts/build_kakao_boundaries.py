"""Build Kakao collection boundaries from the bundled administrative-dong GeoJSON.

The source file is already WGS84 (CRS84). Its features are administrative
dong/eup/myeon polygons, so they are grouped into the project's municipality
(``region_id``) boundaries before Kakao collection begins.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from apps.api.app.services import regions

DEFAULT_SOURCE = Path("data/HangJeongDong_ver20260701.geojson")
DEFAULT_OUTPUT = Path("data/raw/national_sigungu.geojson")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source = _load_feature_collection(args.source)
    payload = build_boundaries(source["features"], region_rows=regions.all_regions())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(payload['features'])} Kakao municipality boundaries to {args.output}")
    return 0


def build_boundaries(source_features: Iterable[dict[str, Any]], *, region_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge administrative-dong polygons and add collection DB metadata."""
    by_id = {str(row["region_id"]): row for row in region_rows}
    target_by_source_name = _source_name_index(region_rows)
    polygons_by_id: dict[str, list[Any]] = defaultdict(list)
    source_codes_by_id: dict[str, set[str]] = defaultdict(set)
    unmatched: set[str] = set()
    for feature in source_features:
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("Every source feature requires properties and geometry.")
        region_id = _resolve_region_id(properties, by_id, target_by_source_name)
        if region_id is None:
            unmatched.add(str(properties.get("adm_nm") or properties.get("sggnm") or "(unnamed)"))
            continue
        polygons_by_id[region_id].extend(_as_polygons(geometry, region_id=region_id))
        source_code = str(properties.get("sgg") or "").strip()
        if source_code:
            source_codes_by_id[region_id].add(source_code)
    missing = sorted(set(by_id) - set(polygons_by_id))
    if missing or unmatched:
        raise ValueError("The administrative-dong GeoJSON does not cover the project region master. " f"missing_region_ids={missing}; unmatched_source_regions={sorted(unmatched)}")
    output_features = []
    for region_id in sorted(by_id):
        row = by_id[region_id]
        code = regions.tour_api_code(region_id)
        # Kakao collection does not use TourAPI codes. The DB schema still
        # requires stable, non-empty values for regions not yet in TourAPI.
        area_code, sigungu_code = code if code is not None else ("unmapped", region_id)
        output_features.append({
            "type": "Feature",
            "properties": {"region_id": region_id, "area_code": area_code, "sigungu_code": sigungu_code,
                           "province_name": str(row["province_name"]), "region_name": str(row["region_name"]),
                           "source_sgg_codes": sorted(source_codes_by_id[region_id])},
            "geometry": {"type": "MultiPolygon", "coordinates": polygons_by_id[region_id]},
        })
    return {"type": "FeatureCollection", "metadata": {"source": "HangJeongDong_ver20260701.geojson",
            "source_level": "administrative_dong", "output_level": "municipality", "crs": "CRS84 / EPSG:4326",
            "region_count": len(output_features)}, "features": output_features}


def _source_name_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], str]:
    return {(str(row["province_name"]).strip(), str(row["region_name"]).strip()): str(row["region_id"]) for row in rows}


def _resolve_region_id(properties: dict[str, Any], by_id: dict[str, dict[str, Any]], by_name: dict[tuple[str, str], str]) -> str | None:
    source_code = str(properties.get("sgg") or "").strip()
    if source_code in by_id:
        return source_code
    # 행정동 원본은 자치구에 별도 5자리 코드를 주지만, 수집 지역
    # 마스터는 해당 자치시 전체를 끝자리 0 코드로 관리한다.
    parent_city_code = source_code[:4] + "0" if len(source_code) == 5 and source_code.isdigit() else ""
    if parent_city_code in by_id:
        return parent_city_code
    province = str(properties.get("sidonm") or "").strip()
    municipality = str(properties.get("sggnm") or "").strip()
    direct = by_name.get((province, municipality))
    if direct:
        return direct
    # Autonomous districts (e.g. "수원시 장안구") belong to one city ("수원시").
    candidates = [(name, region_id) for (candidate_province, name), region_id in by_name.items()
                  if candidate_province == province and municipality.startswith(name + " ")]
    return max(candidates, default=("", None), key=lambda item: len(item[0]))[1]


def _as_polygons(geometry: dict[str, Any], *, region_id: str) -> list[Any]:
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "Polygon" and isinstance(coordinates, list):
        return [coordinates]
    if geometry.get("type") == "MultiPolygon" and isinstance(coordinates, list):
        return coordinates
    raise ValueError(f"{region_id}: source geometry must be Polygon or MultiPolygon.")


def _load_feature_collection(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Source GeoJSON does not exist: {path}") from exc
    features = payload.get("features") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise ValueError("Source must be a GeoJSON FeatureCollection.")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
