"""Compare tourism-content supply composition and area density by Peer."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


CONTENT_TYPES = (
    "FOOD",
    "ACCOMMODATION",
    "CULTURE_TOURISM",
    "EXPERIENCE_TOURISM",
    "LEISURE_SPORTS",
    "SHOPPING",
)
EARTH_RADIUS_M = 6_371_008.8


def build_relative_supply_report(*, target_region: Mapping[str, Any], peer_regions: Sequence[Mapping[str, Any]],
                                 area_km2_by_region: Mapping[str, float]) -> dict[str, Any]:
    """Find types whose composition or density is lower than each Peer.

    A type is a relative-supply candidate when either its six-type composition
    share or its places-per-100-km² density is lower than at least one Peer.
    This is a descriptive comparison, not a demand or business-success claim.
    """
    target = _normalize_region(target_region, area_km2_by_region)
    peers = [_normalize_region(peer, area_km2_by_region) for peer in peer_regions]
    if not peers:
        raise ValueError("상대적 공급 비교에는 최소 한 개의 Peer 지역이 필요합니다.")
    comparisons: list[dict[str, Any]] = []
    for content_type in CONTENT_TYPES:
        target_metrics = target["metrics"][content_type]
        per_peer = []
        for peer in peers:
            peer_metrics = peer["metrics"][content_type]
            composition_ratio = _ratio(target_metrics["composition_share"], peer_metrics["composition_share"])
            density_ratio = _ratio(target_metrics["density_per_100_km2"], peer_metrics["density_per_100_km2"])
            composition_lower = target_metrics["composition_share"] < peer_metrics["composition_share"]
            density_lower = target_metrics["density_per_100_km2"] < peer_metrics["density_per_100_km2"]
            per_peer.append({
                "peer_region": peer["region_name"],
                "peer_composition_share": peer_metrics["composition_share"],
                "peer_density_per_100_km2": peer_metrics["density_per_100_km2"],
                "target_to_peer_composition_ratio": composition_ratio,
                "target_to_peer_density_ratio": density_ratio,
                "is_target_composition_lower": composition_lower,
                "is_target_density_lower": density_lower,
                "is_relative_supply_gap_candidate": composition_lower or density_lower,
            })
        candidate_rows = [item for item in per_peer if item["is_relative_supply_gap_candidate"]]
        comparable_ratios = [
            ratio for item in candidate_rows
            for ratio in (item["target_to_peer_composition_ratio"], item["target_to_peer_density_ratio"])
            if isinstance(ratio, (int, float))
        ]
        comparisons.append({
            "content_type": content_type,
            "target_place_count": target_metrics["place_count"],
            "target_composition_share": target_metrics["composition_share"],
            "target_density_per_100_km2": target_metrics["density_per_100_km2"],
            "individual_peer_comparisons": per_peer,
            "candidate_peer_regions": [item["peer_region"] for item in candidate_rows],
            "candidate_peer_count": len(candidate_rows),
            "lowest_target_to_peer_supply_ratio": min(comparable_ratios, default=None),
        })
    comparisons.sort(key=lambda item: (
        -item["candidate_peer_count"],
        item["lowest_target_to_peer_supply_ratio"] is None,
        item["lowest_target_to_peer_supply_ratio"] or float("inf"),
        item["content_type"],
    ))
    incomplete = [item["region_name"] for item in [target, *peers] if not item["is_complete"]]
    warnings = [
        "비교 지역은 구조적 유사도와 관광 성과 점수로 선정한 유사 지역입니다.",
        "카카오 수집이 불완전한 지역: " + ", ".join(incomplete),
    ] if incomplete else ["비교 지역은 구조적 유사도와 관광 성과 점수로 선정한 유사 지역입니다."]
    return {
        "analysis_type": "relative_supply_gap_by_individual_peer",
        "status": "provisional",
        "target_region": _region_summary(target),
        "peer_regions": [_region_summary(peer) for peer in peers],
        "comparison_rule": "각 유사 지역과 비교해 유형별 공급 구성비 또는 100㎢당 공급밀도가 낮으면 상대적 빈칸 후보로 표시합니다.",
        "content_type_comparisons": comparisons,
        "priority_order_by_relative_supply_gap": [
            item["content_type"] for item in comparisons if item["candidate_peer_count"]
        ],
        "limitations": warnings,
    }


def load_collection_region(path: Path, region_name: str) -> dict[str, Any]:
    payload = _load_json(path)
    for region in payload.get("regions", []):
        if isinstance(region, dict) and region.get("region_name") == region_name:
            return region
    raise ValueError(f"{path}에서 {region_name} 카카오 수집 결과를 찾지 못했습니다.")


def load_region_areas_km2(path: Path, region_names: Sequence[str]) -> dict[str, float]:
    payload = _load_json(path)
    wanted = set(region_names)
    areas: dict[str, float] = {}
    for feature in payload.get("features", []):
        if not isinstance(feature, dict):
            continue
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            continue
        name = str(properties.get("region_name", "")).strip()
        if name in wanted:
            area = _geometry_area_m2(feature.get("geometry")) / 1_000_000
            if area > 0:
                areas[name] = round(area, 6)
    missing = wanted - areas.keys()
    if missing:
        raise ValueError("행정경계 면적을 찾지 못했습니다: " + ", ".join(sorted(missing)))
    return areas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare tourism-content composition and density against individual Peers.")
    parser.add_argument("--target-collection", required=True, type=Path)
    parser.add_argument("--peer-collection", required=True, type=Path)
    parser.add_argument("--boundary-file", required=True, type=Path)
    parser.add_argument("--target-region", required=True)
    parser.add_argument("--peer-region", action="append", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        peer_names = list(dict.fromkeys(args.peer_region))
        target = load_collection_region(args.target_collection, args.target_region)
        peers = [load_collection_region(args.peer_collection, name) for name in peer_names]
        areas = load_region_areas_km2(args.boundary_file, [args.target_region, *peer_names])
        result = build_relative_supply_report(target_region=target, peer_regions=peers, area_km2_by_region=areas)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved relative supply report: {args.output}")
    return 0


def _normalize_region(region: Mapping[str, Any], areas: Mapping[str, float]) -> dict[str, Any]:
    name = str(region.get("region_name", "")).strip()
    counts = region.get("content_type_counts")
    if not name or not isinstance(counts, Mapping) or name not in areas:
        raise ValueError("지역명, 유형별 장소 수, 면적이 필요합니다.")
    normalized_counts = {content_type: _nonnegative_int(counts.get(content_type), content_type) for content_type in CONTENT_TYPES}
    total = sum(normalized_counts.values())
    if total <= 0:
        raise ValueError(f"{name}의 관광 콘텐츠 장소 수 합계가 0입니다.")
    area = float(areas[name])
    if area <= 0:
        raise ValueError(f"{name}의 면적은 양수여야 합니다.")
    return {
        "region_name": name, "area_km2": round(area, 6), "total_place_count": total,
        "is_complete": bool(region.get("is_complete", False)),
        "metrics": {
            content_type: {
                "place_count": count,
                "composition_share": round(count / total, 6),
                "density_per_100_km2": round(count / area * 100, 6),
            }
            for content_type, count in normalized_counts.items()
        },
    }


def _region_summary(region: Mapping[str, Any]) -> dict[str, Any]:
    return {key: region[key] for key in ("region_name", "area_km2", "total_place_count", "is_complete")}


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} 장소 수는 0 이상의 정수여야 합니다.")
    return value


def _ratio(target: float, peer: float) -> float | None:
    return round(target / peer, 1) if peer else None


def _geometry_area_m2(geometry: Any) -> float:
    if not isinstance(geometry, Mapping):
        return 0.0
    coordinates = geometry.get("coordinates")
    if geometry.get("type") == "Polygon" and isinstance(coordinates, list):
        return _polygon_area_m2(coordinates)
    if geometry.get("type") == "MultiPolygon" and isinstance(coordinates, list):
        return sum(_polygon_area_m2(polygon) for polygon in coordinates if isinstance(polygon, list))
    return 0.0


def _polygon_area_m2(rings: list[Any]) -> float:
    if not rings:
        return 0.0
    outer = _ring_area_m2(rings[0])
    holes = sum(_ring_area_m2(ring) for ring in rings[1:] if isinstance(ring, list))
    return max(0.0, outer - holes)


def _ring_area_m2(ring: list[Any]) -> float:
    if len(ring) < 3:
        return 0.0
    area = 0.0
    for current, following in zip(ring, ring[1:] + ring[:1]):
        if not (isinstance(current, list) and isinstance(following, list) and len(current) >= 2 and len(following) >= 2):
            return 0.0
        lon1, lat1 = map(math.radians, (float(current[0]), float(current[1])))
        lon2, lat2 = map(math.radians, (float(following[0]), float(following[1])))
        area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return abs(area) * EARTH_RADIUS_M ** 2 / 2


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} JSON은 객체여야 합니다.")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
