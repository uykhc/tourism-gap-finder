"""Combine a target and structural-peer supply-pressure reports for AI input."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .navigation_demand import (
    DEFAULT_TAXONOMY_PATH,
    build_supply_pressure_report,
    import_navigation_demand_csv,
    load_navigation_demand_taxonomy,
)
from .kakao_supply import PostgresKakaoSupplyProvider


DEFAULT_MAX_COMPARISON_PEERS = 3


def build_peer_supply_pressure_comparison(
    target_report: dict[str, Any], *, peer_reports: list[dict[str, Any]], peer_regions: list[str],
    max_peers: int = DEFAULT_MAX_COMPARISON_PEERS,
) -> dict[str, Any]:
    if len(peer_reports) != len(peer_regions) or not peer_reports:
        raise ValueError("Peer 리포트와 지역명은 하나 이상, 같은 개수여야 합니다.")
    if max_peers < 1:
        raise ValueError("max_peers는 1 이상이어야 합니다.")
    # Candidate lists are pre-ranked by structural similarity. Use only the
    # highest-ranked entries so the statistic and AI context describe the same
    # bounded comparison set.
    peer_reports = peer_reports[:max_peers]
    peer_regions = peer_regions[:max_peers]
    target_context = _context(target_report)
    peer_metrics = [_metrics(report) for report in peer_reports]
    target_metrics = _metrics(target_report)
    content_types = [metric["content_type"] for metric in target_context["content_type_metrics"]]
    comparisons = []
    for content_type in content_types:
        target = target_metrics[content_type]
        individual_comparisons = []
        for peer_region, metrics in zip(peer_regions, peer_metrics, strict=True):
            peer_pressure = metrics[content_type]["searches_per_place"]
            ratio = round(target["searches_per_place"] / peer_pressure, 4) if peer_pressure else None
            individual_comparisons.append({
                "peer_region": peer_region,
                "peer_searches_per_place": peer_pressure,
                "target_to_peer_ratio": ratio,
                "is_target_pressure_at_least_peer": bool(
                    (ratio is not None and ratio >= 1) or (peer_pressure == 0 and target["searches_per_place"] > 0)
                ),
            })
        candidate_ratios = [
            item["target_to_peer_ratio"] for item in individual_comparisons
            if item["is_target_pressure_at_least_peer"] and item["target_to_peer_ratio"] is not None
        ]
        candidate_peers = [item["peer_region"] for item in individual_comparisons if item["is_target_pressure_at_least_peer"]]
        comparisons.append({
            "content_type": content_type,
            "target_searches_per_place": target["searches_per_place"],
            "individual_peer_comparisons": individual_comparisons,
            "candidate_peer_regions": candidate_peers,
            "candidate_peer_count": len(candidate_peers),
            "max_target_to_peer_ratio": max(candidate_ratios, default=None),
        })
    comparisons.sort(key=lambda item: (
        not item["candidate_peer_count"],
        -(item["max_target_to_peer_ratio"] or 0),
        item["content_type"],
    ))
    warning = (
        "Peer는 구조적 유사 후보이며 관광 성과 검증 전입니다. 전국 percentile도 아직 산출하지 않았습니다."
    )
    incomplete_regions = [
        str(report.get("region_name", ""))
        for report in [target_report, *peer_reports]
        if not bool((report.get("data_quality") or {}).get("kakao_supply_is_complete", False))
    ]
    kakao_warning = (
        "카카오 공급 수집에 잘린 타일이 있어 "
        + ", ".join(name for name in incomplete_regions if name)
        + "의 공급압력 비교는 잠정값입니다."
        if incomplete_regions else ""
    )
    target_context = dict(target_context)
    target_context.update({
        "peer_regions": peer_regions,
        "peer_count": len(peer_regions),
        "peer_supply_pressure_comparison": comparisons,
        "priority_order_by_individual_peer_pressure": [
            item["content_type"] for item in comparisons if item["candidate_peer_count"]
        ],
        "limitation": f"{target_context.get('limitation', '')} {warning} {kakao_warning}".strip(),
    })
    return {
        "report_version": "2026-09-05",
        "region_name": target_report.get("region_name"),
        "analysis_period": target_report.get("analysis_period"),
        "selection_type": "structural_similarity_candidates",
        "peer_regions": peer_regions,
        "target_report": target_report,
        "peer_reports": peer_reports,
        "peer_supply_pressure_comparison": comparisons,
        "ai_report_context": target_context,
        "data_quality": {"warnings": [item for item in [warning, kakao_warning] if item]},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build target-vs-peer supply-pressure context for an AI pilot report.")
    parser.add_argument("--target-report", required=True, type=Path)
    parser.add_argument("--peer", action="append", required=True, help="REGION_ID,REGION_NAME=monthly_csv_path; repeat for each peer.")
    parser.add_argument("--max-peers", type=int, default=DEFAULT_MAX_COMPARISON_PEERS)
    parser.add_argument("--content-database-url", help="Postgres URL. Defaults to CONTENT_DATABASE_URL.")
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY_PATH)
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--period-start-ym", help="Period-total CSV start month in YYYYMM.")
    parser.add_argument("--period-end-ym", help="Period-total CSV end month in YYYYMM.")
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = _load_json(args.target_report)
        taxonomy = load_navigation_demand_taxonomy(args.taxonomy)
        database_url = args.content_database_url or os.getenv("CONTENT_DATABASE_URL", "")
        peer_specs = [_parse_peer(raw_peer) for raw_peer in args.peer]
        provider = PostgresKakaoSupplyProvider(
            database_url,
            required_region_ids=tuple(item[0] for item in peer_specs),
            require_complete=True,
        )
        names, reports = [], []
        for region_id, name, path in peer_specs:
            demand_import = import_navigation_demand_csv(
                path,
                region_name=name,
                taxonomy=taxonomy,
                period_start_ym=args.period_start_ym,
                period_end_ym=args.period_end_ym,
            )
            reports.append(build_supply_pressure_report(
                demand_import, taxonomy=taxonomy, supply_provider=provider,
                region_id=region_id, month_count=args.months,
            ))
            names.append(name)
        result = build_peer_supply_pressure_comparison(
            target, peer_reports=reports, peer_regions=names, max_peers=args.max_peers,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved peer comparison: {args.output}")
    return 0


def _parse_peer(value: str) -> tuple[str, str, Path]:
    identity, separator, raw_path = value.partition("=")
    region_id, comma, name = identity.partition(",")
    if not separator or not comma or not region_id.strip() or not name.strip() or not raw_path.strip():
        raise ValueError("--peer는 REGION_ID,REGION_NAME=monthly_csv_path 형식이어야 합니다.")
    return region_id.strip(), name.strip(), Path(raw_path.strip())


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("리포트 JSON은 객체여야 합니다.")
    return payload


def _context(report: dict[str, Any]) -> dict[str, Any]:
    context = report.get("ai_report_context")
    if not isinstance(context, dict) or not isinstance(context.get("content_type_metrics"), list):
        raise ValueError("리포트에 ai_report_context.content_type_metrics가 필요합니다.")
    return context


def _metrics(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = report.get("content_type_metrics")
    if not isinstance(metrics, list):
        raise ValueError("리포트에 content_type_metrics가 필요합니다.")
    result = {item.get("content_type"): item for item in metrics if isinstance(item, dict)}
    if len(result) != 6 or any(not isinstance(item.get("searches_per_place"), (int, float)) for item in result.values()):
        raise ValueError("리포트의 6개 유형 공급압력 지표가 올바르지 않습니다.")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
