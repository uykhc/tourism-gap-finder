"""분석 산출물을 읽어 공개 API 계약으로 옮긴다.

분석 작업은 변하지 않는 JSON 파일을 남긴다. 키가 필요한 느린 수집 작업을
요청 처리 중에 다시 돌리는 것보다 그 파일을 읽는 편이 안전하다.

산출물과 지역을 잇는 키는 `region_id`다. 파일명이나 한국어 지역명으로 잇지
않는다 — 중구가 5곳, 서구·남구·북구가 4곳이라 이름으로 조인하면 값이 섞인다.
이름만 들어 있는 산출물은 그 지역의 peer 후보 집합 안에서만 해석하고,
확정할 수 없으면 값을 만들지 않고 빼면서 그 사실을 함께 돌려준다.
"""

from __future__ import annotations

import copy
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from . import regions as region_table
from .errors import report_not_ready

APP_ROOT = Path(__file__).resolve().parents[1]

#: 기본 산출물 루트는 앱 안이라 배포 이미지에 그대로 실린다. 실제 분석 결과는
#: `ANALYSIS_ARTIFACT_ROOT`로 다른 경로를 가리켜 덮어쓴다.
ARTIFACT_ROOT = Path(os.getenv("ANALYSIS_ARTIFACT_ROOT", APP_ROOT / "data" / "artifacts"))

PEER_CANDIDATES_DIR = "peer_candidates"
RELATIVE_SUPPLY_DIR = "relative_supply"
DATALAB_NAVIGATION_DIR = "datalab_navigation"
AI_REPORTS_DIR = "ai_reports"
PERFORMANCE_DIR = "performance"
PORTFOLIOS_DIR = "portfolios"
HUBS_DIR = "hubs"
RELEASE_MANIFEST = "release-manifest.json"

#: 유사도 패키지 `provenance.py`가 실제로 내보내는 뱃지 값.
_SOURCE_TYPES = {
    "실데이터": "real",
    "proxy": "proxy",
    "정적참조": "static_reference",
    "MOCK": "mock",
}


@lru_cache(maxsize=64)
def _read_cached(path_str: str, mtime_ns: int) -> dict[str, Any]:
    """mtime을 키에 넣어, 개발 중 파일을 고치면 캐시가 저절로 무효화된다."""
    del mtime_ns
    path = Path(path_str)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(503, detail=f"분석 산출물을 읽을 수 없습니다: {path.name}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(503, detail=f"분석 산출물이 객체가 아닙니다: {path.name}")
    return payload


def _read(path: Path) -> dict[str, Any]:
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError as exc:
        raise HTTPException(503, detail=f"분석 산출물을 읽을 수 없습니다: {path.name}") from exc
    # 캐시된 원본을 핸들러가 변형할 수 없도록 사본을 돌려준다.
    return copy.deepcopy(_read_cached(str(path), mtime_ns))


def active_root() -> Path:
    """Return the atomically activated release, or the legacy root.

    Production releases are written under ``releases/<release_id>`` and a
    ``current`` symlink is swapped only after validation. Existing development
    fixtures remain readable directly from ``ARTIFACT_ROOT``.
    """
    current = ARTIFACT_ROOT / "current"
    return current.resolve() if current.is_dir() else ARTIFACT_ROOT


def release_manifest() -> dict[str, Any] | None:
    path = active_root() / RELEASE_MANIFEST
    return _read(path) if path.is_file() else None


def _embedded_region_id(payload: dict[str, Any]) -> str | None:
    """산출물이 스스로 밝힌 대상 지역의 region_id."""
    for key in ("target", "target_region"):
        value = payload.get(key)
        if isinstance(value, dict):
            region_id = str(value.get("region_id") or "").strip()
            if region_id:
                return region_id
    region_id = str(payload.get("region_id") or "").strip()
    return region_id or None


def _embedded_region_name(payload: dict[str, Any]) -> str | None:
    """`region_id`를 내보내지 않는 생산자를 위한 차선책."""
    for key in ("target", "target_region"):
        value = payload.get(key)
        if isinstance(value, dict):
            name = str(value.get("region_name") or "").strip()
            if name:
                return name
    for candidate in (payload, payload.get("report")):
        if isinstance(candidate, dict):
            name = str(candidate.get("region_name") or "").strip()
            if name:
                return name
    return None


def _matches_region(payload: dict[str, Any], region_id: str, region_name: str) -> bool:
    embedded_id = _embedded_region_id(payload)
    if embedded_id is not None:
        # region_id를 밝힌 산출물은 그 값만 믿는다. 다른 지역의 파일이 이름만
        # 같아서 통과하는 일이 없다.
        return embedded_id == region_id
    name = _embedded_region_name(payload)
    if name is None:
        return False
    # 이름만 있는 산출물은 전국이 아니라 이 지역 하나로 좁혀 확인한다.
    return name == region_name


def _find_artifact(region_id: str, directory: str) -> dict[str, Any] | None:
    """해당 지역의 산출물 중 가장 최근 것. 없으면 `None`.

    파일명 규칙에 기대지 않는다. 디렉터리의 JSON을 읽어 산출물이 스스로
    밝힌 대상 지역으로 판단한다.
    """
    region = region_table.find_region(region_id)
    if region is None:
        return None
    directory_path = active_root() / directory
    if not directory_path.is_dir():
        return None
    exact = directory_path / f"{region_id}.json"
    if exact.is_file():
        payload = _read(exact)
        return payload if _matches_region(payload, region_id, region["region_name"]) else None
    paths = sorted(
        directory_path.glob("*.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for path in paths:
        payload = _read(path)
        if _matches_region(payload, region_id, region["region_name"]):
            return payload
    return None


def require_region(region_id: str) -> dict[str, Any]:
    """존재하지 않는 `region_id`만 404다."""
    region = region_table.find_region(region_id)
    if region is None:
        raise HTTPException(404, detail=f"Unknown region_id: {region_id}")
    return region


# ---------------------------------------------------------------------------
# 산출물 로더 — 없으면 None을 돌려주고, 404로 만들지는 호출측이 정한다.
# ---------------------------------------------------------------------------
def load_peer_candidates(region_id: str) -> dict[str, Any] | None:
    return _find_artifact(region_id, PEER_CANDIDATES_DIR)


def load_relative_supply(region_id: str) -> dict[str, Any] | None:
    return _find_artifact(region_id, RELATIVE_SUPPLY_DIR)


def load_supply_pressure(region_id: str) -> dict[str, Any] | None:
    return _find_artifact(region_id, DATALAB_NAVIGATION_DIR)


def load_ai_report(region_id: str) -> dict[str, Any] | None:
    payload = _find_artifact(region_id, AI_REPORTS_DIR)
    if payload is None:
        return None
    report = payload.get("report")
    return report if isinstance(report, dict) else None


def load_performance(region_id: str) -> dict[str, Any] | None:
    return _find_artifact(region_id, PERFORMANCE_DIR)


def load_portfolio(region_id: str) -> dict[str, Any] | None:
    return _find_artifact(region_id, PORTFOLIOS_DIR)


def load_hubs(region_id: str) -> dict[str, Any] | None:
    return _find_artifact(region_id, HUBS_DIR)


def performance_score(region_id: str) -> dict[str, Any]:
    require_region(region_id)
    payload = load_performance(region_id)
    if payload is None:
        report_not_ready(region_id, [PERFORMANCE_DIR])
    value = payload.get("performance")
    if not isinstance(value, dict):
        raise HTTPException(503, detail=f"성과 산출물 형식이 올바르지 않습니다: {region_id}")
    return value


def portfolio_report(region_id: str) -> dict[str, Any]:
    require_region(region_id)
    payload = load_portfolio(region_id)
    if payload is None:
        report_not_ready(region_id, [PORTFOLIOS_DIR])
    value = payload.get("portfolio")
    if not isinstance(value, dict):
        raise HTTPException(503, detail=f"포트폴리오 산출물 형식이 올바르지 않습니다: {region_id}")
    return value


def hub_report(region_id: str, *, base_year_month: str, limit: int) -> dict[str, Any]:
    require_region(region_id)
    payload = load_hubs(region_id)
    if payload is None:
        report_not_ready(region_id, [HUBS_DIR])
    value = payload.get("hubs")
    if not isinstance(value, dict):
        raise HTTPException(503, detail=f"중심 관광지 산출물 형식이 올바르지 않습니다: {region_id}")
    if value.get("base_year_month") != base_year_month:
        report_not_ready(region_id, [f"{HUBS_DIR}:{base_year_month}"])
    spots = list(value.get("spots", []))[:limit]
    return {**value, "limit": limit, "extracted_count": len(spots), "spots": spots}


def comparison(region_ids: list[str]) -> dict[str, Any]:
    regions = [require_region(region_id) for region_id in region_ids]
    first_peers = load_peer_candidates(region_ids[0])
    if first_peers is None:
        report_not_ready(region_ids[0], [PEER_CANDIDATES_DIR])
    similarity = {
        str(item.get("region_id")): float(item["similarity"])
        for item in first_peers.get("peers", [])
        if isinstance(item, dict) and item.get("region_id") and item.get("similarity") is not None
    }
    columns: list[dict[str, Any]] = []
    for index, (region_id, region) in enumerate(zip(region_ids, regions, strict=True)):
        portfolio = portfolio_report(region_id)
        performance = performance_score(region_id)
        columns.append({
            "region": region,
            "area_square_km": portfolio.get("area_square_km"),
            "total_resource_count": portfolio.get("total_resource_count"),
            "total_count_per_square_km": portfolio.get("total_count_per_square_km"),
            "composite_score": performance.get("composite_score"),
            "similarity_to_first": None if index == 0 else similarity.get(region_id),
            "portfolio_metrics": portfolio.get("metrics", []),
        })
    return {
        "columns": columns,
        "limitations": [
            "성과와 관광자원 지표는 release manifest에 기록된 동일 분석 버전의 사전 산출물입니다."
        ],
    }


def peer_region_ids(region_id: str) -> set[str]:
    """이 지역의 peer 후보 `region_id` 집합. 이름 해석의 후보 집합이 된다."""
    payload = load_peer_candidates(region_id)
    if payload is None:
        return set()
    return {
        str(item["region_id"]).strip()
        for item in payload.get("peers", [])
        if isinstance(item, dict) and str(item.get("region_id") or "").strip()
    }


def resolve_peer_regions(
    names: list[str], *, candidate_region_ids: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """지역명 목록을 지역 정보로 바꾼다. `(확정된 지역, 확정하지 못한 이름)`.

    확정할 수 없는 이름은 빼고 그 이름을 함께 돌려준다. 예전 구현은 대상
    지역 자신을 대신 넣어, 자기 자신과 비교한 값이 응답에 섞여 들어갔다.
    """
    resolved: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for name in names:
        peer_id = region_table.resolve_by_name(name, candidate_region_ids=candidate_region_ids)
        if peer_id is None:
            peer_id = region_table.resolve_by_name(name)
        region = None if peer_id is None else region_table.find_region(peer_id)
        if region is None:
            unresolved.append(name)
            continue
        resolved.append(region)
    return resolved, unresolved


# ---------------------------------------------------------------------------
# 엔드포인트 뷰
# ---------------------------------------------------------------------------
def peers(region_id: str, *, k: int, min_similarity: float) -> dict[str, Any]:
    require_region(region_id)
    payload = load_peer_candidates(region_id)
    if payload is None:
        report_not_ready(region_id, [PEER_CANDIDATES_DIR])
    selected = [
        item for item in payload.get("peers", [])
        if isinstance(item, dict) and float(item.get("similarity", 0.0)) >= min_similarity
    ][:k]
    return {
        **payload,
        "requested_k": k,
        "min_similarity": min_similarity,
        "peers": selected,
        "provenance": [_provenance_record(item) for item in payload.get("provenance", [])],
    }


def _provenance_record(item: dict[str, Any]) -> dict[str, Any]:
    row_count = item.get("행수")
    if isinstance(row_count, str):
        # 생산자는 행수를 모르면 빈 문자열을 쓴다. 0으로 바꾸면 '자료 없음'이
        # '0건'이 되므로 null로 둔다.
        row_count = int(row_count) if row_count.strip().isdigit() else None
    return {
        "name": item.get("소스", "분석 산출물"),
        "source_type": _SOURCE_TYPES.get(item.get("신뢰도"), "static_reference"),
        "endpoint": item.get("엔드포인트/출처", ""),
        "reference_period": item.get("기준시점", ""),
        "row_count": row_count,
        "note": item.get("비고", ""),
    }


def supply_pressure_view(target_report: dict[str, Any], *, region_name: str) -> dict[str, Any]:
    """공급압력 산출물의 target_report를 API 응답 조각으로 옮긴다."""
    context = target_report.get("ai_report_context") or {}
    return {
        "report_version": target_report.get("report_version", ""),
        "region_name": target_report.get("region_name", region_name),
        "analysis_period": target_report.get("analysis_period"),
        "metric_definition": context.get("metric_definition", ""),
        "content_type_metrics": target_report.get("content_type_metrics", []),
        "priority_order_by_supply_pressure": context.get("priority_order_by_supply_pressure", []),
        "warnings": (target_report.get("data_quality") or {}).get("warnings", []),
    }


def require_target_report(pressure: dict[str, Any]) -> dict[str, Any]:
    target_report = pressure.get("target_report")
    if not isinstance(target_report, dict):
        raise HTTPException(502, detail="공급압력 산출물에 target_report가 없습니다.")
    return target_report


def gaps(region_id: str) -> dict[str, Any]:
    region = require_region(region_id)
    relative = load_relative_supply(region_id)
    pressure = load_supply_pressure(region_id)
    missing = [
        name for name, value in (("상대적 공급", relative), ("공급압력", pressure)) if value is None
    ]
    if missing or relative is None or pressure is None:
        report_not_ready(region_id, missing)
    target_report = require_target_report(pressure)
    peer_names = [
        str(item.get("region_name") or "").strip()
        for item in relative.get("peer_regions", [])
        if isinstance(item, dict)
    ]
    resolved_peers, unresolved = resolve_peer_regions(
        peer_names, candidate_region_ids=peer_region_ids(region_id)
    )
    limitations = list(relative.get("limitations", []))
    if unresolved:
        limitations.append(
            "비교 지역명을 region_id로 확정할 수 없어 제외했습니다: " + ", ".join(unresolved)
        )
    return {
        "target": region,
        "relative_supply": {
            **relative,
            "target_region": region,
            "peer_regions": resolved_peers,
            "limitations": limitations,
        },
        "supply_pressure": supply_pressure_view(target_report, region_name=region["region_name"]),
    }
