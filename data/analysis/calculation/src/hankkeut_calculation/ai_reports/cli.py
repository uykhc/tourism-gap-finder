"""CLI for a bounded, source-grounded tourism-gap pilot report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .case_search import CaseSearchDocument, SourceKind, screen_case_documents
from .openai_report import (
    DEFAULT_MAX_GAP_TYPES,
    DEFAULT_MODEL,
    OpenAITourismReportGenerator,
    OpenAIWebCaseSearchProvider,
    collect_approved_case_sources,
    create_openai_client,
)
from .report_store import AIReportStore
from ..tourism_data.config import resolve_service_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a source-grounded provisional tourism-gap report.")
    parser.add_argument("--supply-pressure-report", required=True, type=Path)
    parser.add_argument("--relative-supply-report", type=Path, help="Optional individual-Peer composition/density comparison JSON.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--region-id", required=True, help="Five-digit municipality identifier.")
    parser.add_argument("--content-database-url", help="Supabase Postgres URL. Defaults to CONTENT_DATABASE_URL.")
    parser.add_argument("--peer-region", action="append", default=[], help="Verified peer region; first three are used.")
    parser.add_argument("--case-documents", type=Path, help="JSON array of pre-reviewed CaseSearchDocument objects.")
    parser.add_argument("--search-cases", action="store_true", help="Use OpenAI web search for selected types and verified peers.")
    parser.add_argument("--max-gap-types", type=int, default=DEFAULT_MAX_GAP_TYPES)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        supply_report = _load_json(args.supply_pressure_report)
        context = dict(supply_report["ai_report_context"])
        if args.relative_supply_report:
            relative_supply = _load_json(args.relative_supply_report)
            if relative_supply.get("target_region", {}).get("region_name") != context.get("region_name"):
                raise ValueError("상대적 공급 리포트의 타겟 지역이 수요 대비 공급압력 리포트와 다릅니다.")
            comparisons = relative_supply.get("content_type_comparisons")
            if not isinstance(comparisons, list):
                raise ValueError("상대적 공급 리포트에 content_type_comparisons가 필요합니다.")
            context["relative_supply_comparison"] = comparisons
            context["relative_supply_priority"] = relative_supply.get("priority_order_by_relative_supply_gap", [])
            context["limitation"] = (
                f"{context.get('limitation', '')} "
                f"{' '.join(relative_supply.get('limitations', []))}"
            ).strip()
        client = create_openai_client()
        if args.search_cases and not args.peer_region:
            raise ValueError("--search-cases에는 최소 한 개의 검증된 --peer-region이 필요합니다.")
        sources = _load_approved_sources(args.case_documents)
        if args.search_cases:
            priority = (
                context["priority_order_by_individual_peer_pressure"]
                if "priority_order_by_individual_peer_pressure" in context
                else context["priority_order_by_supply_pressure"]
            )
            peer_comparison = context.get("peer_supply_pressure_comparison")
            if isinstance(peer_comparison, list):
                candidate_types = {
                    item.get("content_type") for item in peer_comparison
                    if isinstance(item, dict)
                    and isinstance(item.get("candidate_peer_count"), int)
                    and item["candidate_peer_count"] > 0
                }
                priority = [content_type for content_type in priority if content_type in candidate_types]
            sources = collect_approved_case_sources(
                OpenAIWebCaseSearchProvider(client, model=args.model),
                content_types=priority[:args.max_gap_types],
                peer_regions=args.peer_region,
            )
        result = OpenAITourismReportGenerator(client, model=args.model).generate(
            ai_report_context=context, peer_regions=args.peer_region,
            approved_sources=sources, max_gap_types=args.max_gap_types,
        )
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}")
        return 2
    envelope = {
        "generator": {"model": result.model, "response_id": result.response_id},
        "report": result.report,
    }
    try:
        database_url = args.content_database_url or resolve_content_database_url()
        AIReportStore(database_url).save(region_id=args.region_id, envelope=envelope)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved report: {args.output}")
    return 0


def resolve_content_database_url() -> str:
    return resolve_service_key(
        env_names=("CONTENT_DATABASE_URL", "AUTH_DATABASE_URL"),
    ) or ""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("공급압력 리포트 JSON은 객체여야 합니다.")
    return payload


def _load_approved_sources(path: Path | None):
    if path is None:
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("case-documents JSON은 배열이어야 합니다.")
    documents = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("case-documents 항목은 객체여야 합니다.")
        try:
            documents.append(CaseSearchDocument(
                title=str(item["title"]), url=str(item["url"]), publisher=str(item["publisher"]),
                source_kind=SourceKind(str(item["source_kind"])), snippet=str(item["snippet"]),
                published_at=str(item["published_at"]) if item.get("published_at") else None,
            ))
        except (KeyError, ValueError) as exc:
            raise ValueError("case-documents 항목 형식이 올바르지 않습니다.") from exc
    return screen_case_documents(documents)


if __name__ == "__main__":
    raise SystemExit(main())
