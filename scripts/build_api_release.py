"""Validate and atomically activate a nationwide precomputed API release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from apps.api.app.schemas.analysis import PerformanceScore, PortfolioReport
from apps.api.app.schemas.reports import RegionReport
from apps.api.app.services import artifacts, regions, report
from hankkeut_calculation.ai_reports.report_schema import validate_report_payload

REQUIRED_CSV_COLUMNS = {"기준연월", "목적지 유형", "목적지 검색량"}
ARTIFACT_DIRECTORIES = (
    artifacts.PEER_CANDIDATES_DIR,
    artifacts.RELATIVE_SUPPLY_DIR,
    artifacts.DATALAB_NAVIGATION_DIR,
    artifacts.AI_REPORTS_DIR,
    artifacts.PERFORMANCE_DIR,
    artifacts.PORTFOLIOS_DIR,
    artifacts.HUBS_DIR,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--artifact-root", type=Path, default=Path("data/releases"))
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/datalab_navigation"))
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--pipeline-config",
        type=Path,
        help="JSON stage configuration; commands run per region before validation.",
    )
    parser.add_argument("--cache-root", type=Path, default=Path("data/cache"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    release_root = args.artifact_root / "releases" / args.release_id
    release_root.mkdir(parents=True, exist_ok=True)
    previous = _load_json(release_root / artifacts.RELEASE_MANIFEST) or {}
    previous_by_id = {
        item.get("region_id"): item
        for item in previous.get("regions", [])
        if isinstance(item, dict)
    }
    stages = _load_pipeline_config(args.pipeline_config)
    rows = []
    for region_id in regions.all_region_ids():
        if args.retry_failed and previous_by_id.get(region_id, {}).get("status") == "complete":
            rows.append(previous_by_id[region_id])
            continue
        stage_records, stage_errors = _run_pipeline(
            region_id=region_id,
            stages=stages,
            raw_root=args.raw_root,
            release_root=release_root,
            cache_root=args.cache_root,
        )
        rows.append(_validate_region(
            region_id,
            args.raw_root,
            release_root,
            stage_records=stage_records,
            initial_errors=stage_errors,
        ))
    status = "complete" if rows and all(item["status"] == "complete" for item in rows) else "failed"
    manifest = {
        "manifest_version": "1.0",
        "release_id": args.release_id,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "region_count": len(rows),
        "complete_count": sum(item["status"] == "complete" for item in rows),
        "failed_count": sum(item["status"] == "failed" for item in rows),
        "source_version": args.release_id,
        "analysis_code_version": os.getenv("ANALYSIS_CODE_VERSION", "working-tree"),
        "regions": rows,
    }
    _write_json(release_root / artifacts.RELEASE_MANIFEST, manifest)
    if args.activate:
        if status != "complete" or len(rows) != 230:
            print("release activation refused: all 230 regions must be complete")
            return 2
        _activate(args.artifact_root, release_root)
    print(json.dumps({key: manifest[key] for key in ("release_id", "status", "complete_count", "failed_count")}, ensure_ascii=False))
    return 0 if status == "complete" else 1


def _validate_region(
    region_id: str,
    raw_root: Path,
    release_root: Path,
    *,
    stage_records: list[dict[str, Any]] | None = None,
    initial_errors: list[str] | None = None,
) -> dict[str, Any]:
    errors = list(initial_errors or [])
    csv_path = raw_root / region_id / "navigation.csv"
    input_sha256: str | None = None
    try:
        input_sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            columns = set(next(csv.reader(handle)))
        if not REQUIRED_CSV_COLUMNS.issubset(columns):
            errors.append("raw_csv: required columns missing")
    except (OSError, StopIteration):
        errors.append("raw_csv: missing or empty")

    for directory in ARTIFACT_DIRECTORIES:
        path = release_root / directory / f"{region_id}.json"
        if not path.is_file():
            errors.append(f"{directory}: missing")

    if not errors:
        try:
            with _artifact_root(release_root):
                ai_payload = _load_json(release_root / artifacts.AI_REPORTS_DIR / f"{region_id}.json")
                if not isinstance(ai_payload, dict) or not isinstance(ai_payload.get("report"), dict):
                    raise ValueError("AI report envelope is invalid")
                validate_report_payload(ai_payload["report"])
                PortfolioReport.model_validate(artifacts.portfolio_report(region_id))
                PerformanceScore.model_validate(artifacts.performance_score(region_id))
                compiled = RegionReport.model_validate(report.build_region_report(region_id))
                if not compiled.benchmark_cases or not compiled.recommended_actions or not compiled.sources:
                    raise ValueError("report cases, recommendations, and sources must be non-empty")
        except Exception as exc:  # validation boundary: record every producer/schema failure
            errors.append(f"validation: {type(exc).__name__}: {exc}")
    return {
        "region_id": region_id,
        "status": "failed" if errors else "complete",
        "errors": errors,
        "input": {"path": str(csv_path), "sha256": input_sha256},
        "stages": stage_records or [],
    }


def _load_pipeline_config(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = _load_json(path)
    if payload is None or not isinstance(payload.get("stages"), list):
        raise SystemExit("pipeline config must contain a stages array")
    stages: list[dict[str, Any]] = []
    names: set[str] = set()
    for raw in payload["stages"]:
        if not isinstance(raw, dict):
            raise SystemExit("each pipeline stage must be an object")
        name = str(raw.get("name", "")).strip()
        command = raw.get("command")
        outputs = raw.get("outputs", [])
        if not name or name in names:
            raise SystemExit("pipeline stage names must be non-empty and unique")
        if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
            raise SystemExit(f"pipeline stage {name}: command must be a string array")
        if not isinstance(outputs, list) or not all(isinstance(v, str) for v in outputs):
            raise SystemExit(f"pipeline stage {name}: outputs must be a string array")
        timeout = raw.get("timeout_seconds", 1800)
        if not isinstance(timeout, int) or timeout < 1:
            raise SystemExit(f"pipeline stage {name}: timeout_seconds must be positive")
        names.add(name)
        stages.append({"name": name, "command": command, "outputs": outputs, "timeout_seconds": timeout})
    return stages


def _run_pipeline(
    *,
    region_id: str,
    stages: list[dict[str, Any]],
    raw_root: Path,
    release_root: Path,
    cache_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not stages:
        return [], []
    checkpoint_path = release_root / "checkpoints" / f"{region_id}.json"
    checkpoint = _load_json(checkpoint_path) or {"region_id": region_id, "stages": {}}
    prior = checkpoint.get("stages") if isinstance(checkpoint.get("stages"), dict) else {}
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    region = regions.find_region(region_id)
    values = {
        "region_id": region_id,
        "region_name": region["region_name"] if region else region_id,
        "raw_csv": str(raw_root / region_id / "navigation.csv"),
        "release_root": str(release_root),
        "cache_root": str(cache_root),
    }
    raw_csv = raw_root / region_id / "navigation.csv"
    input_sha256 = hashlib.sha256(raw_csv.read_bytes()).hexdigest() if raw_csv.is_file() else None
    cache_root.mkdir(parents=True, exist_ok=True)
    log_root = release_root / "logs" / region_id
    log_root.mkdir(parents=True, exist_ok=True)
    for stage in stages:
        name = stage["name"]
        outputs = [release_root / value.format_map(values) for value in stage["outputs"]]
        command = [value.format_map(values) for value in stage["command"]]
        fingerprint = hashlib.sha256(json.dumps({
            "command": command,
            "input_sha256": input_sha256,
            "analysis_code_version": os.getenv("ANALYSIS_CODE_VERSION", "working-tree"),
        }, sort_keys=True).encode()).hexdigest()
        old = prior.get(name) if isinstance(prior, dict) else None
        if (
            isinstance(old, dict)
            and old.get("status") == "complete"
            and old.get("fingerprint") == fingerprint
            and all(path.is_file() for path in outputs)
        ):
            records.append(old)
            continue
        started_at = datetime.now(UTC).isoformat(timespec="seconds")
        env = os.environ.copy()
        env["HANKKEUT_CACHE_ROOT"] = str(cache_root)
        try:
            completed = subprocess.run(
                command,
                cwd=Path.cwd(),
                env=env,
                text=True,
                capture_output=True,
                timeout=stage["timeout_seconds"],
                check=False,
            )
            log_path = log_root / f"{name}.log"
            log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
            missing_outputs = [str(path) for path in outputs if not path.is_file()]
            ok = completed.returncode == 0 and not missing_outputs
            record = {
                "name": name,
                "status": "complete" if ok else "failed",
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "return_code": completed.returncode,
                "fingerprint": fingerprint,
                "log": str(log_path),
                "outputs": [str(path) for path in outputs],
                "missing_outputs": missing_outputs,
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            record = {
                "name": name,
                "status": "failed",
                "started_at": started_at,
                "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "error": f"{type(exc).__name__}: {exc}",
                "fingerprint": fingerprint,
                "outputs": [str(path) for path in outputs],
            }
        records.append(record)
        prior[name] = record
        checkpoint["stages"] = prior
        _write_json(checkpoint_path, checkpoint)
        if record["status"] != "complete":
            errors.append(f"stage {name}: failed")
            break
    return records, errors


@contextmanager
def _artifact_root(root: Path) -> Iterator[None]:
    original = artifacts.ARTIFACT_ROOT
    artifacts.ARTIFACT_ROOT = root
    artifacts._read_cached.cache_clear()
    try:
        yield
    finally:
        artifacts.ARTIFACT_ROOT = original
        artifacts._read_cached.cache_clear()


def _activate(root: Path, release_root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    current = root / "current"
    temporary = root / ".current.next"
    if temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(release_root.resolve(), target_is_directory=True)
    os.replace(temporary, current)


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
