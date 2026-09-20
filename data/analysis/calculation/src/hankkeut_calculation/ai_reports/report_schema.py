"""Semantic validation for the strict JSON report contract.

The JSON Schema is the portable contract. This module additionally validates
cross-references that JSON Schema cannot express, such as source IDs used by cases.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

#: Canonical tourism content type codes.  Korean labels live in
#: ``CONTENT_TYPE_LABELS`` and are used only for human-facing text such as web
#: search queries -- never as an identifier or a join key.
CONTENT_TYPES = frozenset({
    "FOOD",
    "ACCOMMODATION",
    "CULTURE_TOURISM",
    "EXPERIENCE_TOURISM",
    "LEISURE_SPORTS",
    "SHOPPING",
})

CONTENT_TYPE_LABELS = {
    "FOOD": "음식",
    "ACCOMMODATION": "숙박",
    "CULTURE_TOURISM": "문화관광",
    "EXPERIENCE_TOURISM": "체험관광",
    "LEISURE_SPORTS": "레저스포츠",
    "SHOPPING": "쇼핑",
}
ROOT_KEYS = frozenset({
    "region_name", "analysis_period", "status", "gap_types",
    "recommended_actions", "sources", "limitations",
})


def validate_report_payload(payload: dict[str, Any]) -> None:
    _require_exact_keys(payload, ROOT_KEYS, "report")
    _require_nonempty_string(payload["region_name"], "region_name")
    _validate_period(payload["analysis_period"])
    if payload["status"] not in {"provisional", "final"}:
        raise ValueError("status는 provisional 또는 final이어야 합니다.")
    if not isinstance(payload["limitations"], list) or not all(isinstance(item, str) and item.strip() for item in payload["limitations"]):
        raise ValueError("limitations는 비어 있지 않은 문자열 배열이어야 합니다.")
    source_ids = _validate_sources(payload["sources"])
    case_titles = _validate_gap_types(payload["gap_types"], source_ids)
    _validate_actions(payload["recommended_actions"], case_titles)


def _validate_sources(value: Any) -> set[str]:
    if not isinstance(value, list):
        raise ValueError("sources는 배열이어야 합니다.")
    source_ids: set[str] = set()
    allowed = frozenset({"source_id", "title", "publisher", "url", "published_at"})
    for index, source in enumerate(value):
        if not isinstance(source, dict):
            raise ValueError(f"sources[{index}]는 객체여야 합니다.")
        _require_exact_keys(source, allowed, f"sources[{index}]")
        source_id = _require_nonempty_string(source["source_id"], f"sources[{index}].source_id")
        if source_id in source_ids:
            raise ValueError("sources.source_id는 중복될 수 없습니다.")
        source_ids.add(source_id)
        _require_nonempty_string(source["title"], f"sources[{index}].title")
        _require_nonempty_string(source["publisher"], f"sources[{index}].publisher")
        url = _require_nonempty_string(source["url"], f"sources[{index}].url")
        if urlparse(url).scheme != "https":
            raise ValueError(f"sources[{index}].url은 HTTPS URL이어야 합니다.")
        _require_nonempty_string(source["published_at"], f"sources[{index}].published_at")
    return source_ids


def _validate_gap_types(value: Any, source_ids: set[str]) -> set[str]:
    # A valid comparison may produce no type above the gap threshold.  An empty
    # array is preferable to inventing a lowest-risk or highest-ranked gap.
    if not isinstance(value, list):
        raise ValueError("gap_types는 배열이어야 합니다.")
    seen_types: set[str] = set()
    case_titles: set[str] = set()
    allowed = frozenset({"content_type", "judgement", "integrated_insight", "quantitative_evidence", "peer_cases", "applicability_insight"})
    for index, gap_type in enumerate(value):
        if not isinstance(gap_type, dict):
            raise ValueError(f"gap_types[{index}]는 객체여야 합니다.")
        _require_exact_keys(gap_type, allowed, f"gap_types[{index}]")
        content_type = _require_nonempty_string(gap_type["content_type"], f"gap_types[{index}].content_type")
        if content_type not in CONTENT_TYPES or content_type in seen_types:
            raise ValueError("gap_types.content_type은 정의된 유형 중 중복 없이 하나여야 합니다.")
        seen_types.add(content_type)
        _require_nonempty_string(gap_type["judgement"], f"gap_types[{index}].judgement")
        _require_nonempty_string(gap_type["integrated_insight"], f"gap_types[{index}].integrated_insight")
        _require_nonempty_string(gap_type["applicability_insight"], f"gap_types[{index}].applicability_insight")
        _validate_evidence(gap_type["quantitative_evidence"], index)
        case_titles.update(_validate_cases(gap_type["peer_cases"], source_ids, index))
    return case_titles


def _validate_evidence(value: Any, gap_index: int) -> None:
    if not isinstance(value, list):
        raise ValueError(f"gap_types[{gap_index}].quantitative_evidence는 배열이어야 합니다.")
    allowed = frozenset({"metric", "target_value", "comparison"})
    for index, evidence in enumerate(value):
        if not isinstance(evidence, dict):
            raise ValueError("quantitative_evidence 항목은 객체여야 합니다.")
        _require_exact_keys(evidence, allowed, f"quantitative_evidence[{index}]")
        _require_nonempty_string(evidence["metric"], f"quantitative_evidence[{index}].metric")
        if isinstance(evidence["target_value"], bool) or not isinstance(evidence["target_value"], (int, float)):
            raise ValueError(f"quantitative_evidence[{index}].target_value는 숫자여야 합니다.")
        _require_nonempty_string(evidence["comparison"], f"quantitative_evidence[{index}].comparison")


def _validate_cases(value: Any, source_ids: set[str], gap_index: int) -> set[str]:
    if not isinstance(value, list):
        raise ValueError(f"gap_types[{gap_index}].peer_cases는 배열이어야 합니다.")
    allowed = frozenset({
        "title", "peer_region", "case_type", "period", "operator", "summary", "source_ids"
    })
    titles: set[str] = set()
    for index, case in enumerate(value):
        if not isinstance(case, dict):
            raise ValueError("peer_cases 항목은 객체여야 합니다.")
        _require_exact_keys(case, allowed, f"peer_cases[{index}]")
        for key in ("title", "peer_region", "period", "operator", "summary"):
            _require_nonempty_string(case[key], f"peer_cases[{index}].{key}")
        if case["case_type"] not in {"FACILITY", "PROGRAM"}:
            raise ValueError(f"peer_cases[{index}].case_type이 올바르지 않습니다.")
        titles.add(case["title"])
        case_source_ids = case["source_ids"]
        if not isinstance(case_source_ids, list) or not case_source_ids or not all(isinstance(item, str) and item in source_ids for item in case_source_ids):
            raise ValueError(f"peer_cases[{index}].source_ids는 등록된 source_id를 하나 이상 참조해야 합니다.")
    return titles


def _validate_actions(value: Any, case_titles: set[str]) -> None:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("recommended_actions는 정확히 2개여야 합니다.")
    allowed = frozenset({"title", "rationale", "evidence_texts", "case_titles"})
    for index, action in enumerate(value):
        if not isinstance(action, dict):
            raise ValueError(f"recommended_actions[{index}]는 객체여야 합니다.")
        _require_exact_keys(action, allowed, f"recommended_actions[{index}]")
        for key in ("title", "rationale"):
            _require_nonempty_string(action[key], f"recommended_actions[{index}].{key}")
        evidence = action["evidence_texts"]
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(item, str) and item.strip() for item in evidence
        ):
            raise ValueError("recommended_actions.evidence_texts는 비어 있지 않은 문자열 배열이어야 합니다.")
        titles = action["case_titles"]
        if not isinstance(titles, list) or not all(isinstance(item, str) for item in titles):
            raise ValueError("recommended_actions.case_titles는 등록된 사례 제목만 참조해야 합니다.")


def _validate_period(value: Any) -> None:
    if not isinstance(value, str) or len(value) != 13 or value[6] != "~":
        raise ValueError("analysis_period는 YYYYMM~YYYYMM 형식이어야 합니다.")
    for part in (value[:6], value[7:]):
        if not part.isdigit() or not 1 <= int(part[4:]) <= 12:
            raise ValueError("analysis_period는 유효한 YYYYMM~YYYYMM 형식이어야 합니다.")


def _require_exact_keys(value: dict[str, Any], allowed: frozenset[str], label: str, *, optional: set[str] | None = None) -> None:
    optional = optional or set()
    missing = allowed - optional - set(value)
    unknown = set(value) - allowed
    if missing or unknown:
        raise ValueError(f"{label} 키가 스키마와 다릅니다. missing={sorted(missing)}, unknown={sorted(unknown)}")


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}은 비어 있지 않은 문자열이어야 합니다.")
    return value.strip()
