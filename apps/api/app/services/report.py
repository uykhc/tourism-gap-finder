"""지역 관광 보고서 화면 응답을 조립한다.

판정과 수치는 모두 여기서 확정한다. AI 산출물이 기여하는 것은 산문
(`judgement`, `applicability_insight`)과 사례·출처뿐이다. 정량 근거는 AI가 쓴
자유 서술(`metric`/`target_value`/`comparison`)을 파싱하지 않고 산출물에서 다시
계산한다. 그래야 화면에 나가는 어떤 숫자도 LLM 출력에 의존하지 않는다.

빈칸 후보 판정은 새 임계값을 만들지 않는다. 산출물이 이미 계산해 둔 두 후보
플래그를 조합한다.

- 상대적 공급 후보: `individual_peer_comparisons[].is_relative_supply_gap_candidate`
- 공급압력 후보: `peer_supply_pressure_comparison[].candidate_peer_count`

두 신호가 모두 가리키면 `STRONG_GAP_CANDIDATE`, 한쪽만이면 `NEEDS_REVIEW`,
어느 쪽도 아니면 `NO_CLEAR_GAP`이다.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException

from ..schemas.common import ContentType
from ..schemas.reports import (
    DiagnosisStatus,
    GapSignalLevel,
    KeyMetricCode,
    OneLineReviewSource,
    ReportStatus,
)
from . import artifacts
from .benchmarks import BenchmarkSelection, resolve_benchmarks

#: 조립 규칙이 바뀌면 올린다. 같은 산출물이라도 응답 구조가 달라지기 때문이다.
ASSEMBLER_VERSION = "1.0.0"

CONTENT_TYPES: tuple[str, ...] = tuple(item.value for item in ContentType)

_SIGNAL_ORDER = {
    GapSignalLevel.STRONG_GAP_CANDIDATE: 0,
    GapSignalLevel.NEEDS_REVIEW: 1,
    GapSignalLevel.NO_CLEAR_GAP: 2,
}

CONTENT_TYPE_LABELS = {
    "FOOD": "음식", "ACCOMMODATION": "숙박", "CULTURE_TOURISM": "문화관광",
    "EXPERIENCE_TOURISM": "체험관광", "LEISURE_SPORTS": "레저·스포츠", "SHOPPING": "쇼핑",
}

_PREPARING_REVIEW = "현재 이 지역의 상세 관광 분석을 준비하고 있습니다."
_PLANNED_ANALYSIS_PERIOD = {"start_ym": "202509", "end_ym": "202608", "month_count": 12}

_FACILITY_KEYWORDS = re.compile(r"시설|센터|타워|공원|워크|박물관|미술관|전망|둘레길|전시관")


# ---------------------------------------------------------------------------
# 조립 입력
# ---------------------------------------------------------------------------
def build_region_report(region_id: str) -> dict[str, Any]:
    """존재하지 않는 지역만 404, 산출물이 부족하면 준비 중 보고서다."""
    region = artifacts.require_region(region_id)
    peers = artifacts.load_peer_candidates(region_id)
    relative = artifacts.load_relative_supply(region_id)
    pressure = artifacts.load_supply_pressure(region_id)
    ai_report = artifacts.load_ai_report(region_id)
    if any(value is None for value in (peers, relative, pressure, ai_report)):
        return _preparing_report(region, peers)
    benchmarks = resolve_benchmarks(region_id, relative)

    target_report: dict[str, Any] | None = None
    if pressure is not None:
        target_report = artifacts.require_target_report(pressure)

    signals = _build_signals(relative, pressure, target_report, benchmarks)
    status = _diagnosis_status(relative, pressure, benchmarks, signals)
    primary = _primary_gap_type(pressure, signals) if status is DiagnosisStatus.GAP_FOUND else None

    limitations = _limitations(relative, target_report, ai_report, benchmarks, status)
    priority_codes = [
        str(item["content_type"])
        for item in _priority_content_types(primary, status, signals)[:2]
    ]
    diagnoses, cases = _diagnoses_and_cases(
        ai_report, signals, limitations, allowed_content_types=priority_codes
    )
    actions = _recommended_actions(ai_report, cases)

    return {
        "report_version": _report_version(relative, pressure, ai_report),
        "report_status": _report_status(relative, ai_report, benchmarks).value,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target": region,
        "analysis_period": _analysis_period(target_report),
        "summary": {
            "diagnosis_status": status.value,
            "primary_gap_type": primary,
            "priority_content_types": _priority_content_types(primary, status, signals),
            "one_line_review": _one_line_review(region, ai_report, primary, status, signals),
            "key_metrics": _key_metrics(primary, status, signals),
        },
        "similar_regions": _similar_regions(peers, relative),
        "tourism_type_comparisons": _tourism_type_comparisons(
            region, signals, target_report, pressure, benchmarks
        ),
        "evidence": _evidence(region, primary, status, signals, target_report),
        "category_overview": _category_overview(status, signals),
        "detailed_diagnoses": diagnoses,
        "recommended_actions": actions,
        "benchmark_cases": cases,
        "methodology": _methodology(relative, target_report, benchmarks, limitations),
        "sources": _sources(ai_report),
    }


def _preparing_report(
    region: dict[str, Any], peers: dict[str, Any] | None = None
) -> dict[str, Any]:
    """현재 프론트 계약을 만족하는 사용자용 준비 중 보고서."""
    return {
        "report_version": ASSEMBLER_VERSION,
        "report_status": ReportStatus.PROVISIONAL.value,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "target": region,
        "analysis_period": dict(_PLANNED_ANALYSIS_PERIOD),
        "summary": {
            "diagnosis_status": DiagnosisStatus.INSUFFICIENT_DATA.value,
            "primary_gap_type": None,
            "priority_content_types": [],
            "one_line_review": {
                "text": _PREPARING_REVIEW,
                "source": OneLineReviewSource.TEMPLATE.value,
                "generated_at": None,
            },
            "key_metrics": [],
        },
        "similar_regions": _similar_regions(peers),
        "tourism_type_comparisons": [],
        "evidence": {
            "supply_density": {
                "content_type": "UNKNOWN",
                "target": {
                    "region_id": region["region_id"],
                    "region_name": region["region_name"],
                    "value": 0,
                    "target_to_benchmark_ratio": None,
                },
                "benchmarks": [],
            },
            "searches_per_place": {
                "metric_definition": "상세 분석 준비 중",
                "items": [],
            },
        },
        "category_overview": [],
        "detailed_diagnoses": [],
        "recommended_actions": [],
        "benchmark_cases": [],
        "methodology": {
            "benchmark_selection_rule": "분석 준비가 완료된 후 비교 기준 지역을 선정합니다.",
            "benchmark_selection_note": "현재는 상세 비교 결과를 제공하지 않습니다.",
            "supply_comparison_rule": "비교 기준 지역과 관광 콘텐츠 현황을 비교합니다.",
            "search_pressure_definition": "관광 검색 수요와 관련 콘텐츠 현황을 함께 살펴봅니다.",
            "provisional_notice": None,
            "limitations": [],
        },
        "sources": [],
    }


# ---------------------------------------------------------------------------
# 유형별 신호
# ---------------------------------------------------------------------------
def _build_signals(
    relative: dict[str, Any] | None,
    pressure: dict[str, Any] | None,
    target_report: dict[str, Any] | None,
    benchmarks: BenchmarkSelection,
) -> dict[str, dict[str, Any]]:
    """유형별로 두 신호와 원본 수치를 한곳에 모은다."""
    comparisons = _by_content_type(
        (relative or {}).get("content_type_comparisons", [])
    )
    pressure_candidates = _by_content_type(
        (pressure or {}).get("peer_supply_pressure_comparison", [])
    )
    metrics = _by_content_type((target_report or {}).get("content_type_metrics", []))
    ranks = _search_ranks(metrics)
    benchmark_names = set(benchmarks.names)

    signals: dict[str, dict[str, Any]] = {}
    for content_type in CONTENT_TYPES:
        comparison = comparisons.get(content_type, {})
        # 비교 기준으로 확정된 지역의 행만 쓴다. 산출물에는 있지만 region_id를
        # 확정하지 못한 지역은 개수에도 비율에도 넣지 않는다.
        rows = [
            row for row in comparison.get("individual_peer_comparisons", [])
            if isinstance(row, dict) and row.get("peer_region") in benchmark_names
        ]
        density_ratios = [
            row["target_to_peer_density_ratio"] for row in rows
            if isinstance(row.get("target_to_peer_density_ratio"), (int, float))
        ]
        lower_count = sum(1 for row in rows if row.get("is_relative_supply_gap_candidate"))
        pressure_count = int(pressure_candidates.get(content_type, {}).get("candidate_peer_count") or 0)
        metric = metrics.get(content_type, {})
        signals[content_type] = {
            "content_type": content_type,
            "signal_level": _signal_level(lower_count > 0, pressure_count > 0),
            "supply_place_count": comparison.get("target_place_count"),
            "composition_share": comparison.get("target_composition_share"),
            "supply_density_per_100_km2": comparison.get("target_density_per_100_km2"),
            "lower_benchmark_count": lower_count,
            "total_benchmark_count": len(rows),
            "lowest_benchmark_supply_ratio": min(density_ratios, default=None),
            "searches_per_place": metric.get("searches_per_place"),
            "navigation_search_count": metric.get("navigation_search_count"),
            "supply_place_count_from_navigation": metric.get("kakao_supply_place_count"),
            "search_rank": ranks.get(content_type),
            "benchmark_metrics": _benchmark_metrics(rows, benchmarks),
        }
    return signals


def _signal_level(relative_candidate: bool, pressure_candidate: bool) -> GapSignalLevel:
    if relative_candidate and pressure_candidate:
        return GapSignalLevel.STRONG_GAP_CANDIDATE
    if relative_candidate or pressure_candidate:
        return GapSignalLevel.NEEDS_REVIEW
    return GapSignalLevel.NO_CLEAR_GAP


def _by_content_type(items: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        return {}
    return {
        str(item["content_type"]): item
        for item in items
        if isinstance(item, dict) and item.get("content_type")
    }


def _search_ranks(metrics: dict[str, dict[str, Any]]) -> dict[str, int]:
    """장소당 검색량 내림차순 순위. 생산자에 rank 필드가 없어 여기서 만든다."""
    ranked = sorted(
        (
            (content_type, value["searches_per_place"])
            for content_type, value in metrics.items()
            if isinstance(value.get("searches_per_place"), (int, float))
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return {content_type: index for index, (content_type, _) in enumerate(ranked, start=1)}


# ---------------------------------------------------------------------------
# 진단 상태와 대표 빈칸
# ---------------------------------------------------------------------------
def _diagnosis_status(
    relative: dict[str, Any] | None,
    pressure: dict[str, Any] | None,
    benchmarks: BenchmarkSelection,
    signals: dict[str, dict[str, Any]],
) -> DiagnosisStatus:
    if relative is None or pressure is None or not benchmarks.regions:
        return DiagnosisStatus.INSUFFICIENT_DATA
    if not relative.get("content_type_comparisons"):
        return DiagnosisStatus.INSUFFICIENT_DATA
    if any(
        signal["signal_level"] is GapSignalLevel.STRONG_GAP_CANDIDATE
        for signal in signals.values()
    ):
        return DiagnosisStatus.GAP_FOUND
    return DiagnosisStatus.NO_CLEAR_GAP


def _primary_gap_type(
    pressure: dict[str, Any] | None, signals: dict[str, dict[str, Any]]
) -> str | None:
    """대표 빈칸 유형. 순서는 산출물이 이미 계산한 우선순위를 그대로 쓴다."""
    strong = {
        content_type
        for content_type, signal in signals.items()
        if signal["signal_level"] is GapSignalLevel.STRONG_GAP_CANDIDATE
    }
    if not strong:
        return None
    context = (pressure or {}).get("ai_report_context") or {}
    for content_type in context.get("priority_order_by_individual_peer_pressure", []):
        if content_type in strong:
            return str(content_type)
    for signal in _sorted_signals(signals):
        if signal["content_type"] in strong:
            return str(signal["content_type"])
    return None


def _sorted_signals(signals: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(signal: dict[str, Any]) -> tuple[Any, ...]:
        ratio = signal["lowest_benchmark_supply_ratio"]
        rank = signal["search_rank"]
        return (
            _SIGNAL_ORDER[signal["signal_level"]],
            -signal["lower_benchmark_count"],
            ratio is None,
            ratio if ratio is not None else 0.0,
            rank is None,
            rank if rank is not None else 0,
            signal["content_type"],
        )

    return sorted(signals.values(), key=sort_key)


def _priority_content_types(
    primary: str | None, status: DiagnosisStatus, signals: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the deterministic, non-LLM top-three screen priorities."""
    if status is DiagnosisStatus.INSUFFICIENT_DATA:
        return []
    ordered = _sorted_signals(signals)
    if primary is not None:
        ordered = [signals[primary], *(item for item in ordered if item["content_type"] != primary)]
    return [
        {
            "rank": index,
            "content_type": item["content_type"],
            "signal_level": item["signal_level"].value,
        }
        for index, item in enumerate(ordered[:3], start=1)
    ]


def _similar_regions(
    peers: dict[str, Any] | None, relative: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Expose only the three selected high-performance similar regions."""
    items = (peers or {}).get("peers", [])
    selected_ids = {
        str(item.get("region_id"))
        for item in (relative or {}).get("peer_regions", [])
        if isinstance(item, dict) and item.get("region_id")
    }
    result = []
    for item in sorted(
        (row for row in items if isinstance(row, dict)),
        key=lambda row: (int(row.get("rank", 10**9)), str(row.get("region_id", ""))),
    ):
        if selected_ids and str(item.get("region_id")) not in selected_ids:
            continue
        if not (
            isinstance(item.get("similarity"), (int, float))
            and str(item.get("region_id", "")).isdigit()
        ):
            continue
        result.append({
            "region_id": str(item["region_id"]),
            "province_name": str(item.get("province_name", "")),
            "region_name": str(item.get("region_name", "")),
            "administrative_type": item.get("administrative_type"),
            "rank": int(item["rank"]),
            "similarity": float(item["similarity"]),
        })
    return result[:3]


def _tourism_type_comparisons(
    region: dict[str, Any],
    signals: dict[str, dict[str, Any]],
    target_report: dict[str, Any] | None,
    pressure: dict[str, Any] | None,
    benchmarks: BenchmarkSelection,
) -> list[dict[str, Any]]:
    """Build all six type-by-region comparisons from already persisted inputs."""
    if target_report is None:
        return []
    target_period = target_report.get("analysis_period")
    peer_ids = list((pressure or {}).get("peer_region_ids") or [])
    peer_reports = list((pressure or {}).get("peer_reports") or [])
    pressure_by_id = {
        str(region_id): report
        for region_id, report in zip(peer_ids, peer_reports, strict=False)
        if isinstance(report, dict) and report.get("analysis_period") == target_period
    }
    result: list[dict[str, Any]] = []
    for content_type in CONTENT_TYPES:
        signal = signals[content_type]
        density_target = _numeric_or_none(signal.get("supply_density_per_100_km2"))
        pressure_target = _numeric_or_none(signal.get("searches_per_place"))
        density_by_id = {
            str(row["region_id"]): _numeric_or_none(row.get("value"))
            for row in signal.get("benchmark_metrics", [])
            if isinstance(row, dict) and row.get("region_id")
        }
        pressure_by_peer_id = {
            region_id: _peer_searches_per_place(report, content_type)
            for region_id, report in pressure_by_id.items()
        }
        benchmark_rows = [
            {
                "region_id": item["region_id"],
                "region_name": item["region_name"],
                "value": density_by_id.get(item["region_id"]),
            }
            for item in benchmarks.regions
        ]
        pressure_rows = [
            {
                "region_id": item["region_id"],
                "region_name": item["region_name"],
                "value": pressure_by_peer_id.get(item["region_id"]),
            }
            for item in benchmarks.regions
        ]
        reference = _largest_relative_supply_density_gap(
            density_target, benchmarks.regions, density_by_id
        )
        reference_id = None if reference is None else reference["region_id"]
        density_reference = None if reference_id is None else density_by_id.get(reference_id)
        pressure_reference = None if reference_id is None else pressure_by_peer_id.get(reference_id)
        result.append({
            "content_type": content_type,
            "reference_region": None if reference is None else {
                "region_id": reference["region_id"], "region_name": reference["region_name"],
            },
            "supply_density": {
                "unit": "PLACES_PER_100_KM2",
                "target": {"region_id": region["region_id"], "region_name": region["region_name"], "value": density_target},
                "benchmarks": benchmark_rows,
                "target_to_reference_ratio": _ratio(density_target, density_reference),
            },
            "searches_per_place": {
                "unit": "SEARCHES_PER_PLACE",
                "target": {"region_id": region["region_id"], "region_name": region["region_name"], "value": pressure_target},
                "benchmarks": pressure_rows,
                "target_to_reference_ratio": _ratio(pressure_target, pressure_reference),
            },
        })
    return result


def _peer_searches_per_place(report: dict[str, Any], content_type: str) -> float | None:
    for item in report.get("content_type_metrics", []):
        if isinstance(item, dict) and item.get("content_type") == content_type:
            return _numeric_or_none(item.get("searches_per_place"))
    return None


def _numeric_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _positive(value: float | None) -> bool:
    return value is not None and value > 0


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    return None if numerator is None or denominator is None or denominator == 0 else round(numerator / denominator, 1)


def _largest_relative_supply_density_gap(
    target_value: float | None,
    regions: tuple[dict[str, Any], ...],
    values_by_id: dict[str, float | None],
) -> dict[str, Any] | None:
    """Choose the selected similar region with the largest density ratio gap."""
    if target_value is None or target_value <= 0:
        return None
    comparable = [
        region for region in regions
        if _positive(values_by_id.get(str(region["region_id"])))
    ]
    if not comparable:
        return None
    return max(
        comparable,
        key=lambda region: (
            max(
                target_value / float(values_by_id[str(region["region_id"])]),
                float(values_by_id[str(region["region_id"])]) / target_value,
            ),
            str(region["region_id"]),
        ),
    )


# ---------------------------------------------------------------------------
# 핵심 지표
# ---------------------------------------------------------------------------
def _key_metrics(
    primary: str | None, status: DiagnosisStatus, signals: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    if status is DiagnosisStatus.INSUFFICIENT_DATA:
        return []
    subject = primary
    if subject is None:
        ordered = _sorted_signals(signals)
        subject = str(ordered[0]["content_type"]) if ordered else None
    if subject is None:
        return []
    signal = signals[subject]
    metrics: list[dict[str, Any]] = []

    argmin = _argmin_density_benchmark(signal)
    if argmin is not None:
        row, ratio = argmin
        metrics.append({
            "metric_code": KeyMetricCode.MIN_BENCHMARK_SUPPLY_RATIO.value,
            "content_type": subject,
            "value": ratio,
            "benchmark_region_id": row["region_id"],
            "benchmark_region_name": row["region_name"],
        })
    if signal["total_benchmark_count"]:
        metrics.append({
            "metric_code": KeyMetricCode.LOWER_BENCHMARK_COUNT.value,
            "content_type": subject,
            "value": signal["lower_benchmark_count"],
            "total_benchmark_count": signal["total_benchmark_count"],
        })
    if signal["searches_per_place"] is not None and signal["search_rank"] is not None:
        metrics.append({
            "metric_code": KeyMetricCode.SEARCHES_PER_PLACE.value,
            "content_type": subject,
            "value": signal["searches_per_place"],
            "rank": signal["search_rank"],
            "total_content_type_count": len(CONTENT_TYPES),
        })
    # 위 지표를 못 만들었을 때만 공급 규모로 채운다. 최소 2개는 있어야 한다.
    for code, value in (
        (KeyMetricCode.SUPPLY_PLACE_COUNT, signal["supply_place_count"]),
        (KeyMetricCode.SUPPLY_DENSITY_PER_100_KM2, signal["supply_density_per_100_km2"]),
    ):
        if len(metrics) >= 2:
            break
        if value is not None:
            metrics.append({
                "metric_code": code.value, "content_type": subject, "value": value,
            })
    return metrics[:4]


def _argmin_density_benchmark(signal: dict[str, Any]) -> tuple[dict[str, Any], float] | None:
    """공급밀도 비율이 가장 낮은 비교 기준 지역과 그 비율.

    구성비 비율과 섞지 않는다. 두 기준을 섞어 최솟값을 내면 무엇의 몇 배인지
    알 수 없는 숫자가 된다.
    """
    candidates = [
        (row, float(row["target_to_benchmark_ratio"]))
        for row in signal.get("benchmark_metrics", [])
        if isinstance(row.get("target_to_benchmark_ratio"), (int, float))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[1], item[0]["region_id"]))


# ---------------------------------------------------------------------------
# 근거
# ---------------------------------------------------------------------------
def _benchmark_metrics(
    comparison_rows: list[dict[str, Any]], benchmarks: BenchmarkSelection
) -> list[dict[str, Any]]:
    """비교 기준 지역별 공급밀도와 대상/기준 비율. region_id를 함께 낸다."""
    rows: list[dict[str, Any]] = []
    for row in comparison_rows:
        region = benchmarks.by_name(str(row.get("peer_region")))
        if region is None:
            continue
        value = row.get("peer_density_per_100_km2")
        if not isinstance(value, (int, float)):
            continue
        ratio = row.get("target_to_peer_density_ratio")
        rows.append({
            "region_id": region["region_id"],
            "region_name": region["region_name"],
            "value": value,
            "target_to_benchmark_ratio": round(float(ratio), 1) if isinstance(ratio, (int, float)) else None,
        })
    return rows


def _evidence(
    region: dict[str, Any],
    primary: str | None,
    status: DiagnosisStatus,
    signals: dict[str, dict[str, Any]],
    target_report: dict[str, Any] | None,
) -> dict[str, Any]:
    if status is DiagnosisStatus.INSUFFICIENT_DATA:
        return {"supply_density": None, "searches_per_place": None}
    subject = primary
    if subject is None:
        ordered = _sorted_signals(signals)
        subject = str(ordered[0]["content_type"]) if ordered else None
    supply_density = None
    if subject is not None:
        signal = signals[subject]
        if signal["supply_density_per_100_km2"] is not None:
            supply_density = {
                "content_type": subject,
                "target": {
                    "region_id": region["region_id"],
                    "region_name": region["region_name"],
                    "value": signal["supply_density_per_100_km2"],
                    "target_to_benchmark_ratio": None,
                },
                "benchmarks": signal.get("benchmark_metrics", []),
            }
    context = (target_report or {}).get("ai_report_context") or {}
    items = [
        {
            "content_type": signal["content_type"],
            "navigation_search_count": signal["navigation_search_count"],
            # 생산자의 kakao_supply_place_count를 스펙 필드명으로 옮긴다.
            "supply_place_count": signal["supply_place_count_from_navigation"],
            "searches_per_place": signal["searches_per_place"],
            "rank": signal["search_rank"],
        }
        for signal in sorted(
            signals.values(), key=lambda item: (item["search_rank"] or len(CONTENT_TYPES) + 1)
        )
        if signal["search_rank"] is not None
        and signal["searches_per_place"] is not None
        and signal["navigation_search_count"] is not None
        and signal["supply_place_count_from_navigation"] is not None
    ]
    searches = None
    if items:
        searches = {
            "metric_definition": context.get("metric_definition", ""),
            "items": items,
        }
    return {"supply_density": supply_density, "searches_per_place": searches}


def _category_overview(
    status: DiagnosisStatus, signals: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    if status is DiagnosisStatus.INSUFFICIENT_DATA:
        return []
    return [
        {
            "content_type": signal["content_type"],
            "signal_level": signal["signal_level"].value,
            "supply_place_count": signal["supply_place_count"],
            "composition_share": signal["composition_share"],
            "supply_density_per_100_km2": signal["supply_density_per_100_km2"],
            "lower_benchmark_count": signal["lower_benchmark_count"],
            "total_benchmark_count": signal["total_benchmark_count"],
            "lowest_benchmark_supply_ratio": signal["lowest_benchmark_supply_ratio"],
            "searches_per_place": signal["searches_per_place"],
            "search_rank": signal["search_rank"],
        }
        for signal in _sorted_signals(signals)
    ]


# ---------------------------------------------------------------------------
# 상세 진단과 사례
# ---------------------------------------------------------------------------
def _diagnoses_and_cases(
    ai_report: dict[str, Any] | None,
    signals: dict[str, dict[str, Any]],
    limitations: list[str],
    *,
    allowed_content_types: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if ai_report is None:
        return [], []
    gap_types = ai_report.get("gap_types")
    if not isinstance(gap_types, list) or not gap_types:
        # AI 스키마에서 빈 배열은 적법하다. 판정 문장을 지어내지 않는다.
        return [], []
    source_ids = {
        str(item["source_id"])
        for item in ai_report.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }
    diagnoses: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    case_ids_by_key: dict[tuple[str, str], str] = {}
    allowed = set(allowed_content_types) if allowed_content_types is not None else None
    for gap_type in gap_types:
        if not isinstance(gap_type, dict):
            continue
        content_type = str(gap_type.get("content_type") or "")
        if allowed is not None and content_type not in allowed:
            continue
        signal = signals.get(content_type)
        if signal is None or signal["signal_level"] is GapSignalLevel.NO_CLEAR_GAP:
            continue
        case_ids: list[str] = []
        for case in gap_type.get("peer_cases", []):
            if not isinstance(case, dict):
                continue
            key = (str(case.get("peer_region") or ""), str(case.get("title") or ""))
            case_id = case_ids_by_key.get(key)
            if case_id is None:
                case_source_ids = [
                    str(item) for item in case.get("source_ids", []) if str(item) in source_ids
                ]
                if not case_source_ids:
                    limitations.append(
                        f"출처를 확인할 수 없어 사례를 제외했습니다: {key[1]}"
                    )
                    continue
                case_id = f"case-{len(cases) + 1:02d}"
                case_ids_by_key[key] = case_id
                cases.append({
                    "case_id": case_id,
                    "benchmark_region_name": key[0],
                    "title": key[1],
                    "case_type": str(case.get("case_type") or ""),
                    "content_type": content_type,
                    "period": str(case.get("period") or ""),
                    "operator": str(case.get("operator") or ""),
                    "summary": str(case.get("summary") or ""),
                    "applicability": str(gap_type.get("applicability_insight") or ""),
                    "source_ids": case_source_ids,
                })
            case_ids.append(case_id)
        diagnoses.append({
            "content_type": content_type,
            "signal_level": signal["signal_level"].value,
            "judgement": str(gap_type.get("judgement") or ""),
            "insight": str(gap_type.get("integrated_insight") or gap_type.get("judgement") or ""),
            "quantitative_evidence": _quantitative_evidence(signal),
            "applicability_insight": str(gap_type.get("applicability_insight") or ""),
            "case_ids": case_ids,
        })
    order = {content_type: index for index, content_type in enumerate(allowed_content_types or [])}
    diagnoses.sort(key=lambda item: order.get(str(item["content_type"]), len(order)))
    return diagnoses, cases


def _recommended_actions(
    ai_report: dict[str, Any], cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    case_id_by_title = {item["title"]: item["case_id"] for item in cases}
    actions = ai_report.get("recommended_actions")
    if not isinstance(actions, list) or not actions:
        raise HTTPException(502, detail="AI 보고서에 recommended_actions가 없습니다.")
    result: list[dict[str, Any]] = []
    for order, action in enumerate(actions, start=1):
        if not isinstance(action, dict):
            raise HTTPException(502, detail="AI 보고서의 recommended_actions 형식이 잘못됐습니다.")
        result.append({
            "order": order,
            "content_type": action.get("content_type") if action.get("content_type") in CONTENT_TYPES else None,
            "title": str(action.get("title") or ""),
            "rationale": str(action.get("rationale") or ""),
            "evidence_texts": [str(item) for item in action.get("evidence_texts", [])],
            "case_ids": [
                case_id_by_title[title]
                for title in action.get("case_titles", [])
                if title in case_id_by_title
            ],
        })
    return result


def _quantitative_evidence(signal: dict[str, Any]) -> list[dict[str, Any]]:
    """AI가 쓴 자유 서술을 파싱하지 않고 산출물 수치로 다시 만든다."""
    evidence: list[dict[str, Any]] = []
    if signal["supply_density_per_100_km2"] is not None:
        evidence.append({
            "metric_code": KeyMetricCode.SUPPLY_DENSITY_PER_100_KM2.value,
            "value": signal["supply_density_per_100_km2"],
            "comparisons": [
                {
                    "region_id": row["region_id"],
                    "region_name": row["region_name"],
                    "benchmark_value": row["value"],
                    "target_to_benchmark_ratio": row["target_to_benchmark_ratio"],
                }
                for row in signal.get("benchmark_metrics", [])
            ],
        })
    if signal["searches_per_place"] is not None and signal["search_rank"] is not None:
        evidence.append({
            "metric_code": KeyMetricCode.SEARCHES_PER_PLACE.value,
            "value": signal["searches_per_place"],
            "comparisons": [],
            "rank": signal["search_rank"],
            "total_count": len(CONTENT_TYPES),
        })
    argmin = _argmin_density_benchmark(signal)
    if argmin is not None and signal["total_benchmark_count"] >= 2:
        row, ratio = argmin
        evidence.append({
            "metric_code": KeyMetricCode.MIN_BENCHMARK_SUPPLY_RATIO.value,
            "value": ratio,
            "comparisons": [{
                "region_id": row["region_id"],
                "region_name": row["region_name"],
                "benchmark_value": row["value"],
                "target_to_benchmark_ratio": row["target_to_benchmark_ratio"],
            }],
        })
    return evidence


# ---------------------------------------------------------------------------
# 한줄평
# ---------------------------------------------------------------------------
def _one_line_review(
    region: dict[str, Any],
    ai_report: dict[str, Any] | None,
    primary: str | None,
    status: DiagnosisStatus,
    signals: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """사전 생성 AI 판정의 첫 문장을 쓰고, 없으면 템플릿 문장을 만든다."""
    if primary is not None:
        return {
            "text": f"{region['region_name']}에 필요한 한끗은 {CONTENT_TYPE_LABELS.get(primary, primary)}입니다.",
            "source": OneLineReviewSource.TEMPLATE.value,
            "generated_at": None,
        }
    return {
        "text": _template_review(region, status, primary, signals),
        "source": OneLineReviewSource.TEMPLATE.value,
        "generated_at": None,
    }


def _template_review(
    region: dict[str, Any],
    status: DiagnosisStatus,
    primary: str | None,
    signals: dict[str, dict[str, Any]],
) -> str:
    name = region["region_name"]
    if status is DiagnosisStatus.INSUFFICIENT_DATA:
        return f"{name}는 비교에 필요한 분석 산출물이 아직 없어 빈칸 진단을 제시할 수 없습니다."
    if status is DiagnosisStatus.NO_CLEAR_GAP or primary is None:
        return f"{name}는 비교 기준 지역 대비 뚜렷한 공급 빈칸 신호가 관찰되지 않았습니다."
    signal = signals[primary]
    return (
        f"{name}는 비교 기준 {signal['total_benchmark_count']}곳 중 "
        f"{signal['lower_benchmark_count']}곳보다 해당 유형의 공급밀도가 낮게 관찰됩니다."
    )


# ---------------------------------------------------------------------------
# 방법과 한계
# ---------------------------------------------------------------------------
def _limitations(
    relative: dict[str, Any] | None,
    target_report: dict[str, Any] | None,
    ai_report: dict[str, Any] | None,
    benchmarks: BenchmarkSelection,
    status: DiagnosisStatus,
) -> list[str]:
    lines: list[str] = []
    lines.extend(str(item) for item in (relative or {}).get("limitations", []))
    lines.extend(str(item) for item in ((target_report or {}).get("data_quality") or {}).get("warnings", []))
    lines.extend(str(item) for item in (ai_report or {}).get("limitations", []))
    if benchmarks.unresolved_names:
        lines.append(
            "비교 지역명을 region_id로 확정할 수 없어 제외했습니다: "
            + ", ".join(benchmarks.unresolved_names)
        )
    if status is DiagnosisStatus.INSUFFICIENT_DATA:
        lines.append("비교에 필요한 분석 산출물이 없어 빈칸 진단을 산출하지 않았습니다.")
    return _dedupe([line for line in lines if not _is_redundant_disclaimer(line)])


def _is_redundant_disclaimer(line: str) -> bool:
    normalized = line.replace(" ", "")
    return any(token in normalized for token in ("잠정", "완벽", "전국percentile", "관광성과검증전"))


def _dedupe(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        if line and line not in seen:
            seen.add(line)
            result.append(line)
    return result


def _methodology(
    relative: dict[str, Any] | None,
    target_report: dict[str, Any] | None,
    benchmarks: BenchmarkSelection,
    limitations: list[str],
) -> dict[str, Any]:
    context = (target_report or {}).get("ai_report_context") or {}
    return {
        "benchmark_selection_rule": benchmarks.rule,
        "benchmark_selection_note": benchmarks.note,
        "supply_comparison_rule": (relative or {}).get("comparison_rule")
        or "비교 기준 지역과 유형별 공급 구성비 또는 100㎢당 공급밀도를 비교합니다.",
        "search_pressure_definition": context.get("metric_definition")
        or "유형별 내비게이션 목적지 검색량 ÷ 유형별 등록 장소 수",
        "provisional_notice": None,
        "limitations": limitations,
    }


def _sources(ai_report: dict[str, Any] | None) -> list[dict[str, Any]]:
    sources = (ai_report or {}).get("sources")
    if not isinstance(sources, list):
        return []
    return [item for item in sources if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# 메타
# ---------------------------------------------------------------------------
def _analysis_period(target_report: dict[str, Any] | None) -> dict[str, Any] | None:
    if target_report is None:
        return None
    period = target_report.get("analysis_period")
    if not isinstance(period, dict):
        raise HTTPException(502, detail="공급압력 산출물에 analysis_period가 없습니다.")
    missing = [key for key in ("start_ym", "end_ym", "month_count") if not period.get(key)]
    if missing:
        raise HTTPException(
            502, detail="공급압력 산출물의 analysis_period가 불완전합니다: " + ", ".join(missing)
        )
    return {
        "start_ym": str(period["start_ym"]),
        "end_ym": str(period["end_ym"]),
        "month_count": int(period["month_count"]),
    }


def _report_version(
    relative: dict[str, Any] | None,
    pressure: dict[str, Any] | None,
    ai_report: dict[str, Any] | None,
) -> str:
    stamps = [
        str(value)
        for value in (
            (pressure or {}).get("report_version"),
            (relative or {}).get("report_version"),
            (ai_report or {}).get("report_version"),
        )
        if value
    ]
    return f"{ASSEMBLER_VERSION}+{max(stamps)}" if stamps else ASSEMBLER_VERSION


def _report_status(
    relative: dict[str, Any] | None,
    ai_report: dict[str, Any] | None,
    benchmarks: BenchmarkSelection,
) -> ReportStatus:
    statuses = [
        str((relative or {}).get("status") or "provisional"),
        str((ai_report or {}).get("status") or "provisional"),
    ]
    if benchmarks.performance_backed and all(item == "final" for item in statuses):
        return ReportStatus.FINAL
    return ReportStatus.PROVISIONAL
