"""Report the nationwide Tourism Data Lab CSV intake queue without downloading data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from apps.api.app.services import regions
try:  # module import in tests/package usage
    from scripts.build_release_artifacts import (
        ADVANCED_REPORT_TARGETS,
        select_performance_peers,
    )
except ModuleNotFoundError:  # direct `python scripts/datalab_intake_manifest.py`
    from build_release_artifacts import ADVANCED_REPORT_TARGETS, select_performance_peers


REQUIRED_COLUMNS = {"카테고리중분류명", "유형별 검색건수"}
MONTHLY_COLUMNS = {"기준연월", "목적지 유형", "목적지 검색량"}
EXPECTED_SOURCE_TYPES = {
    "자연관광", "역사관광", "체험관광", "문화관광", "레저스포츠",
    "쇼핑", "음식", "숙박", "기타관광",
}
TARGET_REGION_IDS = ADVANCED_REPORT_TARGETS
START_YM = "202509"
END_YM = "202608"
EXPECTED_MONTHS = (
    "202509", "202510", "202511", "202512", "202601", "202602",
    "202603", "202604", "202605", "202606", "202607", "202608",
)
REGION_ID_COLUMNS = ("region_id", "지역코드", "시군구코드")


def build_manifest(
    raw_root: Path,
    *,
    selected_region_ids: list[str] | tuple[str, ...] | None = None,
    target_peers: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    items = []
    ready_count = 0
    selected = set(selected_region_ids) if selected_region_ids is not None else None
    scoped_regions = [
        region for region in regions.all_regions()
        if selected is None or region["region_id"] in selected
    ]
    for region in scoped_regions:
        path = raw_root / region["region_id"] / "navigation.csv"
        status, detail = validate_csv(path, expected_region_id=region["region_id"])
        if status == "ready":
            ready_count += 1
        items.append({
            "region_id": region["region_id"],
            "province_name": region["province_name"],
            "region_name": region["region_name"],
            "recommended_path": str(path),
            "status": status,
            "detail": detail,
        })
    return {
        "source": "한국관광 데이터랩 내비게이션 유형별 검색건수 기간 합계 CSV",
        "required_columns": sorted(REQUIRED_COLUMNS),
        "analysis_period": {"start_ym": START_YM, "end_ym": END_YM, "month_count": 12},
        "target_region_ids": list(TARGET_REGION_IDS),
        "target_peers": target_peers or {},
        "ready_count": ready_count,
        "required_count": len(items),
        "items": items,
    }


def validate_csv(path: Path, *, expected_region_id: str | None = None) -> tuple[str, str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or ())
            if not REQUIRED_COLUMNS.issubset(columns) and not MONTHLY_COLUMNS.issubset(columns):
                return "invalid", "required columns are missing"
            rows = list(reader)
    except OSError:
        return "missing", "download and place the CSV at the recommended path"
    if not rows:
        return "invalid", "CSV has no data rows"
    if REQUIRED_COLUMNS.issubset(columns):
        source_types: list[str] = []
        for row in rows:
            source_type = str(row.get("카테고리중분류명") or "").strip()
            if not source_type:
                continue
            raw_count = str(row.get("유형별 검색건수") or "").strip().replace(",", "")
            if not raw_count.isdigit():
                return "invalid", f"유형별 검색건수 must be a non-negative integer: {source_type}"
            source_types.append(source_type)
        if len(source_types) != len(set(source_types)):
            return "invalid", "duplicate 카테고리중분류명 rows"
        missing = sorted(EXPECTED_SOURCE_TYPES - set(source_types))
        extra = sorted(set(source_types) - EXPECTED_SOURCE_TYPES)
        if missing or extra:
            return "invalid", f"destination type mismatch; missing={missing}, extra={extra}"
        return "ready", f"9 destination types, period total ({START_YM}~{END_YM})"
    months = {str(row.get("기준연월") or "").strip() for row in rows}
    if any(len(month) != 6 or not month.isdigit() for month in months):
        return "invalid", "기준연월 must use YYYYMM"
    expected_months = set(EXPECTED_MONTHS)
    if months != expected_months:
        missing = sorted(expected_months - months)
        extra = sorted(months - expected_months)
        return "invalid", f"analysis period mismatch; missing={missing}, extra={extra}"
    row_keys = [
        (
            str(row.get("기준연월") or "").strip(),
            str(row.get("목적지 유형") or "").strip(),
        )
        for row in rows
    ]
    if len(row_keys) != len(set(row_keys)):
        return "invalid", "duplicate 기준연월/목적지 유형 rows"
    if expected_region_id:
        region_column = next((name for name in REGION_ID_COLUMNS if name in columns), None)
        if region_column:
            values = {
                str(row.get(region_column) or "").strip()
                for row in rows
                if str(row.get(region_column) or "").strip()
            }
            if values != {expected_region_id}:
                return "invalid", f"region id mismatch: expected {expected_region_id}"
    return "ready", f"{len(rows)} rows, 12 months ({START_YM}~{END_YM})"


def select_download_scope(artifact_root: Path) -> tuple[list[str], dict[str, list[str]]]:
    active_root = (
        (artifact_root / "current").resolve()
        if (artifact_root / "current").is_dir()
        else artifact_root
    )
    target_peers: dict[str, list[str]] = {}
    selected: list[str] = []
    for target_id in TARGET_REGION_IDS:
        peers = select_performance_peers(
            target_id,
            peer_artifact=active_root / "peer_candidates" / f"{target_id}.json",
            performance_dir=active_root / "performance",
            max_peers=3,
        )
        target_peers[target_id] = peers
        selected.extend((target_id, *peers))
    return list(dict.fromkeys(selected)), target_peers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/datalab_navigation"))
    parser.add_argument("--artifact-root", type=Path, default=Path("data/artifacts"))
    parser.add_argument(
        "--all-regions", action="store_true",
        help="List all regions instead of the five advanced-report targets and their peers.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    selected_ids: list[str] | None = None
    target_peers: dict[str, list[str]] | None = None
    if not args.all_regions:
        selected_ids, target_peers = select_download_scope(args.artifact_root)
    payload = build_manifest(
        args.raw_root,
        selected_region_ids=selected_ids,
        target_peers=target_peers,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if payload["ready_count"] == payload["required_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
