"""CLI for collecting major Kakao Local API categories near one tourism point."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .client import CATEGORY_GROUPS, KakaoLocalApiError, KakaoLocalClient
from ..tourism_data.config import resolve_kakao_rest_api_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Kakao place categories near a tourism point.")
    parser.add_argument("--name", required=True, help="Name of the center attraction or area.")
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--radius-meters", type=int, default=2000)
    parser.add_argument("--category", action="append", choices=tuple(CATEGORY_GROUPS), help="Repeat to select categories; defaults to all supported groups.")
    parser.add_argument("--rest-api-key", help="Kakao REST API key; otherwise KAKAO_REST_API_KEY is used.")
    parser.add_argument("--output", type=Path, default=Path("data/analysis/kakao_places"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    key = args.rest_api_key or resolve_kakao_rest_api_key()
    if not key:
        print("Error: provide --rest-api-key or KAKAO_REST_API_KEY.", file=sys.stderr)
        return 2
    try:
        collections = KakaoLocalClient(key).collect_categories_nearby(
            category_group_codes=args.category or tuple(CATEGORY_GROUPS),
            longitude=args.longitude,
            latitude=args.latitude,
            radius_meters=args.radius_meters,
        )
    except (KakaoLocalApiError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    payload = {
        "center_name": args.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Kakao Local API category search",
        "collections": [collection.to_dict() for collection in collections],
    }
    safe_name = "".join(character if character.isalnum() or character in "-_" else "_" for character in args.name).strip("_") or "place"
    path = args.output / f"{safe_name}_kakao_categories.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved: {path}")
    for collection in collections:
        suffix = " (truncated)" if collection.result_truncated else ""
        print(f"{collection.category_group_name}: {collection.collected_count}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
