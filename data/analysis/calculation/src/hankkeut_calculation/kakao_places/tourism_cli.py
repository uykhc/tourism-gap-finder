"""CLI for the six-type tourism-content Kakao collection."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .region_collector import DEFAULT_INITIAL_TILE_METERS, DEFAULT_MIN_TILE_METERS
from .region_cli import _load_features, _region_name
from .content_store import KakaoContentStore
from .tourism_content import (
    DEFAULT_TAXONOMY_PATH,
    KakaoTourismContentCollector,
    load_tourism_content_taxonomy,
)
from .client import KakaoLocalClient
from ..tourism_data.config import resolve_kakao_rest_api_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect six-type tourism content from Kakao Local API.")
    parser.add_argument("--boundaries", required=True, type=Path, help="WGS84 GeoJSON FeatureCollection file.")
    parser.add_argument("--region-name", action="append", default=[], help="Feature region_name to collect; repeatable. Defaults to all.")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY_PATH)
    parser.add_argument("--initial-tile-meters", type=int, default=DEFAULT_INITIAL_TILE_METERS)
    parser.add_argument("--minimum-tile-meters", type=int, default=DEFAULT_MIN_TILE_METERS)
    parser.add_argument("--rest-api-key", help="Overrides KAKAO_REST_API_KEY for this run.")
    parser.add_argument("--content-database-url", help="Postgres URL. Defaults to CONTENT_DATABASE_URL.")
    parser.add_argument("--collector-version", default="kakao-tourism-content/1")
    parser.add_argument("--note", help="Optional collection-run note.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    features = _load_features(args.boundaries)
    requested_names = set(args.region_name)
    selected = [feature for feature in features if not requested_names or _region_name(feature) in requested_names]
    missing_names = requested_names - {_region_name(feature) for feature in selected}
    if missing_names:
        raise SystemExit("Unknown region_name: " + ", ".join(sorted(missing_names)))
    key = args.rest_api_key or resolve_kakao_rest_api_key()
    if not key:
        print("Error: provide --rest-api-key or KAKAO_REST_API_KEY.", file=sys.stderr)
        return 2
    database_url = args.content_database_url or os.getenv("CONTENT_DATABASE_URL") or os.getenv("AUTH_DATABASE_URL")
    if not database_url:
        print("Error: provide --content-database-url or CONTENT_DATABASE_URL.", file=sys.stderr)
        return 2
    taxonomy = load_tourism_content_taxonomy(args.taxonomy)
    collector = KakaoTourismContentCollector(KakaoLocalClient(key), taxonomy)
    try:
        store = KakaoContentStore(database_url)
        run_id = store.start_run(
            taxonomy_version=taxonomy.version,
            collector_version=args.collector_version,
            note=args.note,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    completed = 0
    try:
        for index, feature in enumerate(selected, start=1):
            region = _region_metadata(feature)
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict):
                raise ValueError(f"{region['region_name']}: GeoJSON feature geometry is missing.")
            result = collector.collect_region(
                region_name=region["region_name"],
                geometry=geometry,
                initial_tile_meters=args.initial_tile_meters,
                minimum_tile_meters=args.minimum_tile_meters,
            ).to_dict()
            store.save_region(
                run_id=run_id,
                region=region,
                content_type_counts=result["content_type_counts"],
                is_complete=bool(result["is_complete"]),
                truncated_tile_count=int(result["truncated_tile_count"]),
            )
            completed += 1
            print(f"[{index}/{len(selected)}] stored {region['region_name']}: {result['classified_count']}")
    except Exception as exc:
        store.finish_run(run_id=run_id, status="failed", region_count=completed, note=str(exc))
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    store.finish_run(run_id=run_id, status="completed", region_count=completed)
    print(f"Completed collection run {run_id}: {completed} regions")
    return 0


def _region_metadata(feature: dict[str, object]) -> dict[str, str]:
    properties = feature.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Every boundary feature needs properties.")
    required = ("region_id", "area_code", "sigungu_code", "province_name")
    missing = [key for key in required if not str(properties.get(key, "")).strip()]
    if missing:
        raise ValueError("전국 DB 적재용 GeoJSON properties 누락: " + ", ".join(missing))
    return {
        "region_id": str(properties["region_id"]).strip(),
        "area_code": str(properties["area_code"]).strip(),
        "sigungu_code": str(properties["sigungu_code"]).strip(),
        "province_name": str(properties["province_name"]).strip(),
        "region_name": _region_name(feature),
    }


if __name__ == "__main__":
    raise SystemExit(main())
