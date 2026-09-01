"""CLI for the six-type tourism-content Kakao collection."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .region_collector import DEFAULT_INITIAL_TILE_METERS, DEFAULT_MIN_TILE_METERS
from .region_cli import _load_features, _region_name, _write_json
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
    parser.add_argument("--output", type=Path, default=Path("data/analysis/kakao_regions/kakao_tourism_content.json"))
    parser.add_argument("--checkpoint-dir", type=Path, help="Directory for per-region completed results. Defaults beside --output.")
    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument("--resume", dest="resume", action="store_true", default=True)
    resume_group.add_argument("--no-resume", dest="resume", action="store_false")
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
    taxonomy = load_tourism_content_taxonomy(args.taxonomy)
    collector = KakaoTourismContentCollector(KakaoLocalClient(key), taxonomy)
    checkpoint_dir = args.checkpoint_dir or args.output.parent / f"{args.output.stem}_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for index, feature in enumerate(selected, start=1):
        region_name = _region_name(feature)
        checkpoint_path = checkpoint_dir / _checkpoint_name(index, region_name)
        result = _load_checkpoint(checkpoint_path, taxonomy.version) if args.resume else None
        if result is None:
            geometry = feature.get("geometry")
            if not isinstance(geometry, dict):
                raise SystemExit(f"{region_name}: GeoJSON feature geometry is missing.")
            result = collector.collect_region(
                region_name=region_name,
                geometry=geometry,
                initial_tile_meters=args.initial_tile_meters,
                minimum_tile_meters=args.minimum_tile_meters,
            ).to_dict()
            _write_json(checkpoint_path, result)
            print(f"[{index}/{len(selected)}] saved {region_name}: {result['collected_count']}")
        else:
            print(f"[{index}/{len(selected)}] reused {region_name}")
        results.append(result)
        _write_json(args.output, _payload(args.boundaries, args.taxonomy, results, checkpoint_dir))
    _write_json(args.output, _payload(args.boundaries, args.taxonomy, results, checkpoint_dir))
    return 0


def _checkpoint_name(index: int, region_name: str) -> str:
    safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in region_name)
    return f"{index:03d}_{safe_name}.json"


def _load_checkpoint(path: Path, taxonomy_version: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    required = {"region_name", "taxonomy_version", "content_type_counts", "places"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        return None
    return payload if payload["taxonomy_version"] == taxonomy_version else None


def _payload(boundaries: Path, taxonomy: Path, results: list[dict[str, Any]], checkpoint_dir: Path) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "boundary_file": str(boundaries),
        "taxonomy_file": str(taxonomy),
        "checkpoint_directory": str(checkpoint_dir),
        "regions": results,
    }


if __name__ == "__main__":
    raise SystemExit(main())
