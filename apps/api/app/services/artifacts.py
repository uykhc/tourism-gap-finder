"""Read versioned pipeline artifacts and adapt them to the public API contract.

The analysis jobs write immutable JSON files.  Serving those files is safer
than rerunning slow, key-backed collection jobs in a request handler.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from .. import region_master

REPO_ROOT = Path(__file__).resolve().parents[4]
ARTIFACT_ROOT = Path(os.getenv("ANALYSIS_ARTIFACT_ROOT", REPO_ROOT / "data/analysis"))


def _read(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(503, detail=f"분석 산출물을 읽을 수 없습니다: {path.name}") from exc


def _region(region_id: str) -> dict[str, Any]:
    value = region_master.find_region(region_id)
    if value is not None:
        return value
    # The Swagger seed master is intentionally small.  Until it is replaced by
    # the contracts master, pipeline artifacts themselves are an authoritative
    # fallback for regions they contain.
    for path in (ARTIFACT_ROOT / "peer_candidates").glob("*.json"):
        candidate = _read(path)
        for item in [candidate.get("target"), *candidate.get("peers", [])]:
            if isinstance(item, dict) and item.get("region_id") == region_id:
                return item
    raise HTTPException(404, detail=f"Unknown region_id: {region_id}")


def _region_by_name(region_name: str, fallback: dict[str, Any]) -> dict[str, Any]:
    for path in (ARTIFACT_ROOT / "peer_candidates").glob("*.json"):
        candidate = _read(path)
        for item in [candidate.get("target"), *candidate.get("peers", [])]:
            if isinstance(item, dict) and item.get("region_name") == region_name:
                return item
    return fallback


def _artifact_for(region_id: str, directory: str, marker: str) -> dict[str, Any]:
    region = _region(region_id)
    # File stems are generated from the target's Korean name.  Validate the
    # embedded target as well, so a coincidental filename never leaks data.
    candidates = sorted((ARTIFACT_ROOT / directory).glob(f"*{marker}*.json"), reverse=True)
    for path in candidates:
        value = _read(path)
        target = value.get("target_region") or value.get("target") or value.get("region_name")
        if target is None and isinstance(value.get("report"), dict):
            target = value["report"].get("region_name")
        if isinstance(target, dict):
            target = target.get("region_name")
        if target == region["region_name"]:
            return value
    raise HTTPException(404, detail=f"{region['region_name']}의 {directory} 분석 결과가 없습니다. 분석 작업을 먼저 실행하세요.")


def peers(region_id: str, *, k: int, min_similarity: float) -> dict[str, Any]:
    value = _artifact_for(region_id, "peer_candidates", "structural_peer_candidates")
    values = [p for p in value["peers"] if p["similarity"] >= min_similarity][:k]
    source_types = {"실데이터": "real", "대체값": "proxy", "정적 참조": "static_reference", "모의": "mock"}
    provenance = [
        {
            "name": item.get("소스", "분석 산출물"),
            "source_type": source_types.get(item.get("신뢰도"), "static_reference"),
            "endpoint": item.get("엔드포인트/출처", ""),
            "reference_period": item.get("기준시점", ""),
            "row_count": item.get("행수"),
            "note": item.get("비고", ""),
        }
        for item in value.get("provenance", [])
    ]
    return {**value, "requested_k": k, "min_similarity": min_similarity, "peers": values, "provenance": provenance}


def gaps(region_id: str) -> dict[str, Any]:
    relative = _artifact_for(region_id, "relative_supply", "relative_supply_gap_detailed")
    pressure = _artifact_for(region_id, "datalab_navigation", "individual_supply_pressure_detailed")
    region = _region(region_id)
    target = region
    peers_value = [_region_by_name(item["region_name"], region) for item in relative["peer_regions"]]
    relative_api = {**relative, "target_region": target, "peer_regions": peers_value}
    target_report = pressure["target_report"]
    supply_pressure = {
        "report_version": target_report["report_version"], "region_name": target_report["region_name"],
        "analysis_period": target_report["analysis_period"],
        "metric_definition": target_report["ai_report_context"]["metric_definition"],
        "content_type_metrics": target_report["content_type_metrics"],
        "priority_order_by_supply_pressure": target_report["ai_report_context"]["priority_order_by_supply_pressure"],
        "warnings": target_report["data_quality"]["warnings"],
    }
    return {"target": target, "relative_supply": relative_api, "supply_pressure": supply_pressure}


def report(region_id: str) -> dict[str, Any]:
    """Adapt the AI job output to the stable frontend report contract."""
    ai = _artifact_for(region_id, "ai_reports", "detailed_gap_report_with_cases").get("report", {})
    gap = gaps(region_id)
    peer_result = peers(region_id, k=50, min_similarity=0.0)
    source_ids = {item["source_id"] for item in ai.get("sources", [])}
    cases: list[dict[str, Any]] = []
    gap_types: list[dict[str, Any]] = []
    for gap_type in ai.get("gap_types", []):
        refs = []
        for index, case in enumerate(gap_type.get("peer_cases", []), start=1):
            case_id = f"{gap_type['content_type']}-{index}"
            refs.append({"case_id": case_id, "relevance_note": None})
            cases.append({
                "case_id": case_id, "benchmark_region": case["peer_region"], "title": case["title"],
                "case_type": "프로그램", "content_type": gap_type["content_type"], "period": None,
                "operator": None, "summary": case["summary"],
                "applicability": gap_type["applicability_insight"],
                "source_ids": [sid for sid in case.get("source_ids", []) if sid in source_ids] or [next(iter(source_ids), "unavailable")],
            })
        gap_types.append({**gap_type, "case_refs": refs})
        gap_types[-1].pop("peer_cases", None)
    return {
        "report_version": "artifact", "status": ai.get("status", "provisional"), "target": gap["target"],
        "analysis_period": ai["analysis_period"],
        "headline": ai.get("gap_types", [{}])[0].get("judgement", "분석 결과를 확인하세요."),
        "peers": {"selection_type": peer_result["selection_type"], "note": peer_result["warning"], "items": peer_result["peers"]},
        "benchmarks": {"selection_rule": "성과 데이터 산출 전 구조적 유사 후보를 표시합니다.", "items": []},
        "relative_supply": {"comparison_rule": gap["relative_supply"]["comparison_rule"], "notes": gap["relative_supply"]["limitations"], "content_type_comparisons": gap["relative_supply"]["content_type_comparisons"], "priority_order": gap["relative_supply"]["priority_order_by_relative_supply_gap"]},
        "supply_pressure": {"metric_definition": gap["supply_pressure"]["metric_definition"], "analysis_period": gap["supply_pressure"]["analysis_period"], "notes": gap["supply_pressure"]["warnings"], "content_type_metrics": gap["supply_pressure"]["content_type_metrics"], "priority_order": gap["supply_pressure"]["priority_order_by_supply_pressure"]},
        "gap_types": gap_types, "benchmark_cases": cases,
        "closing_insight": {"narrative": "AI 분석 산출물 기반 관광 콘텐츠 공백 진단입니다.", "focus_points": [], "watch_outs": ai.get("limitations", [])},
        "sources": ai.get("sources", []), "limitations": ai.get("limitations", []),
    }
