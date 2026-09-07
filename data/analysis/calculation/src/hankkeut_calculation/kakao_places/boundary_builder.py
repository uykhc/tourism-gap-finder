"""Build Gyeonggi city/county boundaries from administrative-dong GeoJSON."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_gyeonggi_sigun_boundaries(source: dict[str, Any]) -> dict[str, Any]:
    """Merge administrative-dong features into Gyeonggi's 31 city/county units."""
    features = source.get("features") if isinstance(source, dict) else None
    if source.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise ValueError("Source must be a GeoJSON FeatureCollection.")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in features:
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("Every source feature requires properties and geometry.")
        source_name = properties.get("sggnm")
        if not isinstance(source_name, str) or not source_name.strip():
            raise ValueError("Every source feature requires properties.sggnm.")
        groups[_to_gyeonggi_sigun_name(source_name)].append(feature)

    output_features = []
    for region_name, members in sorted(groups.items()):
        polygons: list[Any] = []
        source_codes: set[str] = set()
        source_names: set[str] = set()
        for member in members:
            properties = member["properties"]
            geometry = member["geometry"]
            source_codes.add(str(properties.get("sgg", "")).strip())
            source_names.add(str(properties.get("sggnm", "")).strip())
            if geometry.get("type") == "Polygon":
                polygons.append(geometry.get("coordinates"))
            elif geometry.get("type") == "MultiPolygon":
                coordinates = geometry.get("coordinates")
                if not isinstance(coordinates, list):
                    raise ValueError(f"{region_name}: invalid MultiPolygon coordinates.")
                polygons.extend(coordinates)
            else:
                raise ValueError(f"{region_name}: only Polygon and MultiPolygon are supported.")
        output_features.append(
            {
                "type": "Feature",
                "properties": {
                    "region_name": region_name,
                    "source_sgg_codes": sorted(code for code in source_codes if code),
                    "source_sgg_names": sorted(name for name in source_names if name),
                    "source_feature_count": len(members),
                },
                "geometry": {"type": "MultiPolygon", "coordinates": polygons},
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "region_level": "gyeonggi_sigun",
            "source_level": "administrative_dong",
            "region_count": len(output_features),
        },
        "features": output_features,
    }


def _to_gyeonggi_sigun_name(sgg_name: str) -> str:
    """Collapse autonomous districts such as '수원시 장안구' into '수원시'."""
    name = sgg_name.strip()
    if name.endswith("구") and "시" in name:
        return name[: name.index("시") + 1]
    return name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build 31 Gyeonggi city/county GeoJSON boundaries.")
    parser.add_argument("--source", required=True, type=Path, help="Administrative-dong GeoJSON with sggnm properties.")
    parser.add_argument("--output", type=Path, default=Path("data/raw/gyeonggi_sigun.geojson"))
    args = parser.parse_args(argv)
    source = json.loads(args.source.read_text(encoding="utf-8"))
    output = build_gyeonggi_sigun_boundaries(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {output['metadata']['region_count']} Gyeonggi city/county boundaries to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
