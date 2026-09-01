"""Command line entry point for municipality-wide Kakao category collection."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import CATEGORY_GROUPS, KakaoLocalClient
from .count_collector import DEFAULT_COUNT_TILE_METERS, DEFAULT_DENSE_TILE_THRESHOLD, KakaoRegionCountCollector
from .region_collector import (
    DEFAULT_INITIAL_TILE_METERS,
    DEFAULT_MIN_TILE_METERS,
    KakaoRegionCollector,
)
from ..tourism_data.config import resolve_kakao_rest_api_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Kakao category places for administrative GeoJSON regions.")
    parser.add_argument("--boundaries", required=True, type=Path, help="WGS84 GeoJSON FeatureCollection file.")
    parser.add_argument("--region-name", action="append", default=[], help="Feature region_name to collect; repeatable. Defaults to all.")
    parser.add_argument("--category", action="append", choices=sorted(CATEGORY_GROUPS), default=[], help="Kakao category code; repeatable. Defaults to all supported codes.")
    parser.add_argument("--initial-tile-meters", type=int, default=DEFAULT_COUNT_TILE_METERS)
    parser.add_argument("--minimum-tile-meters", type=int, default=DEFAULT_MIN_TILE_METERS)
    parser.add_argument("--dense-tile-threshold", type=int, default=DEFAULT_DENSE_TILE_THRESHOLD)
    parser.add_argument("--collection-mode", choices=("count-first", "places"), default="places")
    parser.add_argument("--rest-api-key", help="Overrides KAKAO_REST_API_KEY for this run.")
    parser.add_argument("--output", type=Path, default=Path("data/analysis/kakao_regions/kakao_region_categories.json"))
    parser.add_argument("--checkpoint-dir", type=Path, help="Directory for per-region/category completed results. Defaults beside --output.")
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument("--resume", dest="resume", action="store_true", default=True, help="Reuse completed checkpoints (default).")
    resume_group.add_argument("--no-resume", dest="resume", action="store_false", help="Collect every selected region/category again.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    features = _load_features(args.boundaries)
    requested_names = set(args.region_name)
    selected = [feature for feature in features if not requested_names or _region_name(feature) in requested_names]
    missing_names = requested_names - {_region_name(feature) for feature in selected}
    if missing_names:
        raise SystemExit("Unknown region_name: " + ", ".join(sorted(missing_names)))
    categories = args.category or sorted(CATEGORY_GROUPS)
    key = args.rest_api_key or resolve_kakao_rest_api_key()
    if not key:
        print("Error: provide --rest-api-key or KAKAO_REST_API_KEY.", file=sys.stderr)
        return 2
    client = KakaoLocalClient(key)
    collector = KakaoRegionCountCollector(client) if args.collection_mode == "count-first" else KakaoRegionCollector(client)
    checkpoint_dir = args.checkpoint_dir or args.output.parent / f"{args.output.stem}_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    results = []
    total_jobs = len(selected) * len(categories)
    completed_jobs = 0
    for region_index, feature in enumerate(selected, start=1):
        name = _region_name(feature)
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise SystemExit(f"{name}: GeoJSON feature geometry is missing.")
        category_results = []
        for category in categories:
            checkpoint_path = checkpoint_dir / _checkpoint_name(region_index, name, category)
            checkpoint = _load_checkpoint(checkpoint_path) if args.resume else None
            if checkpoint is not None:
                category_results.append(checkpoint)
                completed_jobs += 1
                print(f"[{completed_jobs}/{total_jobs}] reused {name} / {category}")
                continue
            collection_args = {
                "region_name": name, "geometry": geometry, "category_group_code": category,
                "initial_tile_meters": args.initial_tile_meters, "minimum_tile_meters": args.minimum_tile_meters,
            }
            if args.collection_mode == "count-first":
                collection_args["dense_tile_threshold"] = args.dense_tile_threshold
            result = collector.collect_category(**collection_args).to_dict()
            _write_json(checkpoint_path, result)
            category_results.append(result)
            completed_jobs += 1
            print(f"[{completed_jobs}/{total_jobs}] saved {name} / {category}: {result['collected_count']}")
        results.append({"region_name": name, "categories": category_results})
        _write_json(args.output, _payload(args.boundaries, categories, results, checkpoint_dir, args.collection_mode))
    payload = _payload(args.boundaries, categories, results, checkpoint_dir, args.collection_mode)
    _write_json(args.output, payload)
    print(f"Wrote {len(results)} regions to {args.output}")
    return 0


def _payload(boundaries: Path, categories: list[str], results: list[dict[str, Any]], checkpoint_dir: Path, collection_mode: str) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary_file": str(boundaries),
        "categories": categories,
        "collection_mode": collection_mode,
        "checkpoint_directory": str(checkpoint_dir),
        "regions": results,
    }


def _checkpoint_name(region_index: int, region_name: str, category: str) -> str:
    safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in region_name)
    return f"{region_index:02d}_{safe_name}_{category}.json"


def _load_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    required = {"region_name", "category_group_code", "collected_count"}
    return payload if isinstance(payload, dict) and required.issubset(payload) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _load_features(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Boundary file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Boundary file is not valid JSON: {path}") from exc
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise SystemExit("Boundary file must be a GeoJSON FeatureCollection.")
    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise SystemExit("Boundary GeoJSON must contain at least one feature.")
    valid_features = [feature for feature in features if isinstance(feature, dict)]
    for feature in valid_features:
        _region_name(feature)
    return valid_features


def _region_name(feature: dict[str, Any]) -> str:
    properties = feature.get("properties")
    name = properties.get("region_name") if isinstance(properties, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise SystemExit("Every boundary feature needs properties.region_name.")
    return name.strip()


if __name__ == "__main__":
    raise SystemExit(main())
