"""Create reproducible Data Lab CSV intake tasks from structural peers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_peer_demand_manifest(peer_result: dict[str, Any]) -> dict[str, Any]:
    """Make explicit manual-download tasks without relabeling peers as benchmarks."""
    target = peer_result.get("target")
    peers = peer_result.get("peers")
    if not isinstance(target, dict) or not isinstance(peers, list):
        raise ValueError("Peer 결과 JSON에 target과 peers 배열이 필요합니다.")
    target_name = _required_string(target, "region_name")
    target_id = _required_string(target, "region_id")
    items = []
    seen_ids: set[str] = set()
    for peer in peers:
        if not isinstance(peer, dict):
            raise ValueError("Peer 항목은 객체여야 합니다.")
        region_id = _required_string(peer, "region_id")
        region_name = _required_string(peer, "region_name")
        if region_id == target_id or region_id in seen_ids:
            raise ValueError("Peer region_id는 target과 달라야 하고 중복될 수 없습니다.")
        seen_ids.add(region_id)
        rank = peer.get("rank")
        if isinstance(rank, bool) or not isinstance(rank, int) or rank < 1:
            raise ValueError("Peer rank는 1 이상의 정수여야 합니다.")
        items.append({
            "rank": rank,
            "region_id": region_id,
            "region_name": region_name,
            "similarity": peer.get("similarity"),
            "required_csv_columns": ["기준연월", "목적지 유형", "목적지 검색량"],
            "recommended_raw_directory": f"data/raw/datalab_navigation/peers/{region_id}_{region_name}",
            "required_months": "target과 동일한 최근 12개월(현재 202508~202607)",
            "intake_status": "pending_manual_download",
        })
    if not items:
        raise ValueError("Peer가 없어 데이터랩 입력 목록을 만들 수 없습니다.")
    return {
        "manifest_version": "2026-09-05",
        "target": {"region_id": target_id, "region_name": target_name},
        "selection_type": "structural_similarity_candidates",
        "warning": (
            "이 목록은 구조적으로 유사한 후보입니다. 수요·공급압력과 별도 성과 "
            "검증을 마친 뒤에만 우수 Peer로 승격합니다."
        ),
        "download_instructions": (
            "한국관광 데이터랩에서 각 지역의 '내비게이션 목적지 유형별 검색량'을 "
            "월별 CSV로 내려받아 recommended_raw_directory에 보관하세요."
        ),
        "peer_inputs": sorted(items, key=lambda item: item["rank"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create monthly Data Lab intake tasks for structural peer candidates.")
    parser.add_argument("--peer-result", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.loads(args.peer_result.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Peer 결과 JSON은 객체여야 합니다.")
        manifest = build_peer_demand_manifest(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved peer demand manifest: {args.output}")
    return 0


def _required_string(value: dict[str, Any], key: str) -> str:
    result = str(value.get(key, "")).strip()
    if not result:
        raise ValueError(f"{key}는 비어 있을 수 없습니다.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
