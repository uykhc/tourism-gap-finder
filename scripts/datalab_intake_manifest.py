"""Report the nationwide Tourism Data Lab CSV intake queue without downloading data."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from apps.api.app.services import regions


REQUIRED_COLUMNS = {"기준연월", "목적지 유형", "목적지 검색량"}


def build_manifest(raw_root: Path) -> dict[str, Any]:
    items = []
    ready_count = 0
    for region in regions.all_regions():
        path = raw_root / region["region_id"] / "navigation.csv"
        status, detail = validate_csv(path)
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
        "source": "한국관광 데이터랩 내비게이션 목적지 유형별 검색량 월별 CSV",
        "required_columns": sorted(REQUIRED_COLUMNS),
        "ready_count": ready_count,
        "required_count": len(items),
        "items": items,
    }


def validate_csv(path: Path) -> tuple[str, str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = set(reader.fieldnames or ())
            if not REQUIRED_COLUMNS.issubset(columns):
                return "invalid", "required columns are missing"
            rows = list(reader)
    except OSError:
        return "missing", "download and place the CSV at the recommended path"
    if not rows:
        return "invalid", "CSV has no data rows"
    months = {str(row.get("기준연월") or "").strip() for row in rows}
    if any(len(month) != 6 or not month.isdigit() for month in months):
        return "invalid", "기준연월 must use YYYYMM"
    return "ready", f"{len(rows)} rows, {len(months)} months"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/datalab_navigation"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = build_manifest(args.raw_root)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if payload["ready_count"] == payload["required_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
