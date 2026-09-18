"""Validate and atomically activate a nationwide precomputed API release."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
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
    parser.add_argument(
        "--base-year-month",
        default=os.getenv("ANALYSIS_BASE_YEAR_MONTH", ""),
        help="Hub/report reference month in YYYYMM form (or ANALYSIS_BASE_YEAR_MONTH).",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Check credentials, raw inputs, and artifact coverage without running producers.",
    )
    parser.add_argument(
        "--only-stage",
        action="append",
        default=[],
        help="Run only the named configured stage and validate its declared outputs; repeatable.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    release_root = args.artifact_root / "releases" / args.release_id
    pipeline = _load_pipeline_config(args.pipeline_config)
    if args.preflight:
        result = _preflight(
            raw_root=args.raw_root,
            release_root=release_root,
            pipeline=pipeline,
            base_year_month=args.base_year_month,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ready"] else 1
    if args.activate and args.only_stage:
        raise SystemExit("--activate cannot be combined with --only-stage")

    selected = set(args.only_stage)
    known_names = {
        stage["name"]
        for stage in pipeline["global_stages"] + pipeline["region_stages"]
    }
    unknown = selected - known_names
    if unknown:
        raise SystemExit(f"unknown pipeline stage(s): {', '.join(sorted(unknown))}")

    release_root.mkdir(parents=True, exist_ok=True)
    global_stages = [
        stage for stage in pipeline["global_stages"]
        if not selected or stage["name"] in selected
    ]
    region_stages = [
        stage for stage in pipeline["region_stages"]
        if not selected or stage["name"] in selected
    ]
    global_records, global_errors = _run_global_pipeline(
        stages=global_stages,
        release_root=release_root,
        cache_root=args.cache_root,
        base_year_month=args.base_year_month,
    )
    if selected:
        region_records: dict[str, list[dict[str, Any]]] = {}
        region_errors: dict[str, list[str]] = {}
        if not global_errors:
            for region_id in regions.all_region_ids():
                records, errors = _run_pipeline(
                    region_id=region_id,
                    stages=region_stages,
                    raw_root=args.raw_root,
                    release_root=release_root,
                    cache_root=args.cache_root,
                    base_year_month=args.base_year_month,
                )
                if records:
                    region_records[region_id] = records
                if errors:
                    region_errors[region_id] = errors
        ok = not global_errors and not region_errors
        print(json.dumps({
            "status": "complete" if ok else "failed",
            "selected_stages": sorted(selected),
            "global_stages": global_records,
            "region_count": len(region_records),
            "region_errors": region_errors,
        }, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    previous = _load_json(release_root / artifacts.RELEASE_MANIFEST) or {}
    previous_by_id = {
        item.get("region_id"): item
        for item in previous.get("regions", [])
        if isinstance(item, dict)
    }
    rows = []
    for region_id in regions.all_region_ids():
        if (
            args.retry_failed
            and not global_errors
            and previous_by_id.get(region_id, {}).get("status") == "complete"
        ):
            rows.append(previous_by_id[region_id])
            continue
        stage_records, stage_errors = _run_pipeline(
            region_id=region_id,
            stages=region_stages,
            raw_root=args.raw_root,
            release_root=release_root,
            cache_root=args.cache_root,
            base_year_month=args.base_year_month,
        )
        rows.append(_validate_region(
            region_id,
            args.raw_root,
            release_root,
            stage_records=stage_records,
            initial_errors=global_errors + stage_errors,
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
        "base_year_month": args.base_year_month or None,
        "global_stages": global_records,
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


def _load_pipeline_config(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if path is None:
        return {"global_stages": [], "region_stages": []}
    payload = _load_json(path)
    if payload is None:
        raise SystemExit("pipeline config must be a JSON object")
    legacy = payload.get("stages")
    global_raw = payload.get("global_stages", [])
    region_raw = payload.get("region_stages", legacy if legacy is not None else [])
    if not isinstance(global_raw, list) or not isinstance(region_raw, list):
        raise SystemExit("pipeline config stages must be arrays")
    names: set[str] = set()
    return {
        "global_stages": _parse_stages(global_raw, names),
        "region_stages": _parse_stages(region_raw, names),
    }


def _parse_stages(raw_stages: list[Any], names: set[str]) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    for raw in raw_stages:
        if not isinstance(raw, dict):
            raise SystemExit("each pipeline stage must be an object")
        name = str(raw.get("name", "")).strip()
        command = raw.get("command")
        outputs = raw.get("outputs", [])
        inputs = raw.get("inputs", [])
        requires_any_env = raw.get("requires_any_env", [])
        requires_values = raw.get("requires_values", [])
        requires_raw_csv = raw.get("requires_raw_csv", True)
        requires_postgresql_database = raw.get("requires_postgresql_database", False)
        if not name or name in names:
            raise SystemExit("pipeline stage names must be non-empty and unique")
        if not isinstance(command, list) or not command or not all(isinstance(v, str) for v in command):
            raise SystemExit(f"pipeline stage {name}: command must be a string array")
        if not isinstance(outputs, list) or not all(isinstance(v, str) for v in outputs):
            raise SystemExit(f"pipeline stage {name}: outputs must be a string array")
        if not isinstance(inputs, list) or not all(isinstance(v, str) for v in inputs):
            raise SystemExit(f"pipeline stage {name}: inputs must be a string array")
        if not isinstance(requires_any_env, list) or not all(
            isinstance(group, list) and group and all(isinstance(v, str) for v in group)
            for group in requires_any_env
        ):
            raise SystemExit(f"pipeline stage {name}: requires_any_env must be an array of string arrays")
        if not isinstance(requires_values, list) or not all(isinstance(v, str) for v in requires_values):
            raise SystemExit(f"pipeline stage {name}: requires_values must be a string array")
        if not isinstance(requires_raw_csv, bool):
            raise SystemExit(f"pipeline stage {name}: requires_raw_csv must be boolean")
        if not isinstance(requires_postgresql_database, bool):
            raise SystemExit(
                f"pipeline stage {name}: requires_postgresql_database must be boolean"
            )
        timeout = raw.get("timeout_seconds", 1800)
        if not isinstance(timeout, int) or timeout < 1:
            raise SystemExit(f"pipeline stage {name}: timeout_seconds must be positive")
        names.add(name)
        stages.append({
            "name": name,
            "command": command,
            "outputs": outputs,
            "inputs": inputs,
            "requires_any_env": requires_any_env,
            "requires_values": requires_values,
            "requires_raw_csv": requires_raw_csv,
            "requires_postgresql_database": requires_postgresql_database,
            "timeout_seconds": timeout,
        })
    return stages


def _run_pipeline(
    *,
    region_id: str,
    stages: list[dict[str, Any]],
    raw_root: Path,
    release_root: Path,
    cache_root: Path,
    base_year_month: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    if not stages:
        return [], []
    checkpoint_path = release_root / "checkpoints" / f"{region_id}.json"
    region = regions.find_region(region_id)
    values = {
        "region_id": region_id,
        "region_name": region["region_name"] if region else region_id,
        "raw_csv": str(raw_root / region_id / "navigation.csv"),
        "release_root": str(release_root),
        "cache_root": str(cache_root),
        "repository_root": str(Path.cwd()),
        "python": sys.executable,
        "base_year_month": base_year_month,
    }
    raw_csv = raw_root / region_id / "navigation.csv"
    return _run_stage_sequence(
        stages=stages,
        values=values,
        checkpoint_path=checkpoint_path,
        checkpoint_identity={"region_id": region_id},
        release_root=release_root,
        cache_root=cache_root,
        log_root=release_root / "logs" / region_id,
        default_inputs=[raw_csv],
        global_outputs=False,
    )


def _run_global_pipeline(
    *,
    stages: list[dict[str, Any]],
    release_root: Path,
    cache_root: Path,
    base_year_month: str = "",
) -> tuple[list[dict[str, Any]], list[str]]:
    if not stages:
        return [], []
    values = {
        "release_root": str(release_root),
        "cache_root": str(cache_root),
        "repository_root": str(Path.cwd()),
        "python": sys.executable,
        "base_year_month": base_year_month,
    }
    return _run_stage_sequence(
        stages=stages,
        values=values,
        checkpoint_path=release_root / "checkpoints" / "_global.json",
        checkpoint_identity={"scope": "global"},
        release_root=release_root,
        cache_root=cache_root,
        log_root=release_root / "logs" / "_global",
        default_inputs=[],
        global_outputs=True,
    )


def _run_stage_sequence(
    *,
    stages: list[dict[str, Any]],
    values: dict[str, str],
    checkpoint_path: Path,
    checkpoint_identity: dict[str, str],
    release_root: Path,
    cache_root: Path,
    log_root: Path,
    default_inputs: list[Path],
    global_outputs: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    checkpoint = _load_json(checkpoint_path) or {**checkpoint_identity, "stages": {}}
    prior = checkpoint.get("stages") if isinstance(checkpoint.get("stages"), dict) else {}
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    cache_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    for stage in stages:
        name = stage["name"]
        outputs = _stage_outputs(stage["outputs"], values, release_root, global_outputs)
        command = [value.format_map(values) for value in stage["command"]]
        configured_inputs = [
            Path(value.format_map(values)) for value in stage.get("inputs", [])
        ]
        stage_default_inputs = default_inputs if stage.get("requires_raw_csv", True) else []
        all_inputs = stage_default_inputs + configured_inputs
        input_hashes = _hash_inputs(all_inputs)
        fingerprint = hashlib.sha256(json.dumps({
            "command": command,
            "inputs": input_hashes,
            "analysis_code_version": os.getenv("ANALYSIS_CODE_VERSION", "working-tree"),
        }, sort_keys=True).encode("utf-8")).hexdigest()
        old = prior.get(name) if isinstance(prior, dict) else None
        if (
            isinstance(old, dict)
            and old.get("status") == "complete"
            and old.get("fingerprint") == fingerprint
            and all(path.is_file() for path in outputs)
        ):
            records.append(old)
            continue
        missing_inputs = [str(path) for path in all_inputs if not path.exists()]
        present_env = _configured_env_names()
        missing_env_groups = [
            group for group in stage.get("requires_any_env", [])
            if not any(name in present_env for name in group)
        ]
        missing_values = [
            name for name in stage.get("requires_values", []) if not values.get(name)
        ]
        if stage.get("requires_postgresql_database") and not _postgresql_database_url():
            missing_values.append("postgresql_content_database")
        if missing_inputs or missing_env_groups or missing_values:
            record = {
                "name": name,
                "status": "blocked",
                "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "fingerprint": fingerprint,
                "outputs": [str(path) for path in outputs],
                "missing_inputs": missing_inputs,
                "missing_env_groups": missing_env_groups,
                "missing_values": missing_values,
            }
            records.append(record)
            prior[name] = record
            checkpoint["stages"] = prior
            _write_json(checkpoint_path, checkpoint)
            errors.append(f"stage {name}: blocked by missing prerequisites")
            continue
        started_at = datetime.now(UTC).isoformat(timespec="seconds")
        env = os.environ.copy()
        env["HANKKEUT_CACHE_ROOT"] = str(cache_root)
        dotenv_values = _dotenv_values()
        required_env_names = {
            env_name
            for group in stage.get("requires_any_env", [])
            for env_name in group
        }
        for env_name in required_env_names:
            if not env.get(env_name) and dotenv_values.get(env_name):
                env[env_name] = dotenv_values[env_name]
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
    return records, errors


def _stage_outputs(
    templates: list[str],
    values: dict[str, str],
    release_root: Path,
    expand_regions: bool,
) -> list[Path]:
    outputs: list[Path] = []
    for template in templates:
        if expand_regions and "{region_id}" in template:
            for region_id in regions.all_region_ids():
                outputs.append(release_root / template.format_map({**values, "region_id": region_id}))
        else:
            outputs.append(release_root / template.format_map(values))
    return outputs


def _hash_inputs(paths: list[Path]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for path in paths:
        normalized = path.resolve()
        if normalized.is_file():
            digest = hashlib.sha256(normalized.read_bytes()).hexdigest()
        elif normalized.is_dir():
            hasher = hashlib.sha256()
            for child in sorted(item for item in normalized.rglob("*") if item.is_file()):
                hasher.update(str(child.relative_to(normalized)).encode("utf-8"))
                hasher.update(hashlib.sha256(child.read_bytes()).digest())
            digest = hasher.hexdigest()
        else:
            digest = None
        result[str(normalized)] = digest
    return result


def _preflight(
    *,
    raw_root: Path,
    release_root: Path,
    pipeline: dict[str, list[dict[str, Any]]],
    base_year_month: str = "",
) -> dict[str, Any]:
    env_names = _configured_env_names()
    credential_groups = {
        "tour_api": ("TOUR_API_SERVICE_KEY", "KOR_TOUR_API_SERVICE_KEY"),
        "hub_api": ("TOUR_API_SERVICE_KEY", "HUB_TOUR_API_SERVICE_KEY"),
        "visitor_api": ("TOUR_API_SERVICE_KEY", "VISITOR_API_SERVICE_KEY"),
        "kakao": ("KAKAO_REST_API_KEY",),
        "sgis_key": ("SGIS_CONSUMER_KEY",),
        "sgis_secret": ("SGIS_CONSUMER_SECRET",),
        "openai": ("OPENAI_API_KEY",),
        "content_database": ("CONTENT_DATABASE_URL", "AUTH_DATABASE_URL"),
    }
    credentials = {
        label: any(name in env_names for name in alternatives)
        for label, alternatives in credential_groups.items()
    }
    postgresql_database = _postgresql_database_url()
    region_ids = regions.all_region_ids()
    raw_valid = 0
    raw_invalid: list[str] = []
    for region_id in region_ids:
        path = raw_root / region_id / "navigation.csv"
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                columns = set(next(csv.reader(handle)))
            if REQUIRED_CSV_COLUMNS.issubset(columns):
                raw_valid += 1
            else:
                raw_invalid.append(region_id)
        except (OSError, StopIteration):
            raw_invalid.append(region_id)

    artifact_counts = {
        directory: sum(
            (release_root / directory / f"{region_id}.json").is_file()
            for region_id in region_ids
        )
        for directory in ARTIFACT_DIRECTORIES
    }
    embedded_root = artifacts.APP_ROOT / "data" / "artifacts"
    embedded_counts = {
        directory: len(list((embedded_root / directory).glob("*.json")))
        for directory in ARTIFACT_DIRECTORIES
    }
    unmapped_tour_regions = [
        region_id for region_id in region_ids if regions.tour_api_code(region_id) is None
    ]
    boundary_path = _configured_boundary_path(
        pipeline,
        release_root=release_root,
        cache_root=Path("data/cache"),
        base_year_month=base_year_month,
    )
    boundary_status = _boundary_status(boundary_path, region_ids)
    stage_status = []
    base_values = {
        "release_root": str(release_root),
        "cache_root": str(Path("data/cache")),
        "repository_root": str(Path.cwd()),
        "python": sys.executable,
        "base_year_month": base_year_month,
    }
    for scope in ("global_stages", "region_stages"):
        for stage in pipeline[scope]:
            missing_env_groups = [
                group for group in stage.get("requires_any_env", [])
                if not any(name in env_names for name in group)
            ]
            missing_inputs: list[str] = []
            blocked_region_ids: set[str] = set()
            for template in stage.get("inputs", []):
                if "{region_id}" in template or "{raw_csv}" in template:
                    if scope == "region_stages":
                        for region_id in region_ids:
                            region = regions.find_region(region_id)
                            values = {
                                **base_values,
                                "region_id": region_id,
                                "region_name": region["region_name"] if region else region_id,
                                "raw_csv": str(raw_root / region_id / "navigation.csv"),
                            }
                            if not Path(template.format_map(values)).exists():
                                blocked_region_ids.add(region_id)
                    continue
                path = Path(template.format_map(base_values))
                if not path.exists():
                    missing_inputs.append(str(path))
            if scope == "region_stages" and stage.get("requires_raw_csv", True):
                blocked_region_ids.update(raw_invalid)
            # KorService portfolios need its area/sigungu mapping.  The hub
            # endpoint instead accepts the nationwide legal-dong region id.
            if stage["name"] == "portfolio":
                blocked_region_ids.update(unmapped_tour_regions)
            missing_values = [
                name for name in stage.get("requires_values", []) if not base_values.get(name)
            ]
            if stage.get("requires_postgresql_database") and not postgresql_database:
                missing_values.append("postgresql_content_database")
            stage_status.append({
                "name": stage["name"],
                "scope": "global" if scope == "global_stages" else "region",
                "runnable": (
                    not missing_env_groups
                    and not missing_inputs
                    and not missing_values
                    and not blocked_region_ids
                ),
                "missing_env_groups": missing_env_groups,
                "missing_inputs": missing_inputs,
                "missing_values": missing_values,
                "blocked_region_count": len(blocked_region_ids),
                "blocked_region_ids": sorted(blocked_region_ids),
            })

    release_ready = raw_valid == len(region_ids) and all(
        count == len(region_ids) for count in artifact_counts.values()
    )
    return {
        "ready": release_ready,
        "python": {"executable": sys.executable, "available": Path(sys.executable).is_file()},
        "credentials": credentials,
        "content_database": {
            "configured": credentials["content_database"],
            "postgresql": postgresql_database,
        },
        "analysis_parameters": {
            "base_year_month": base_year_month or None,
            "base_year_month_configured": bool(base_year_month),
        },
        "tour_api_mapping": {
            "mapped_count": len(region_ids) - len(unmapped_tour_regions),
            "missing_region_ids": unmapped_tour_regions,
        },
        "national_boundaries": boundary_status,
        "raw_navigation": {
            "valid_count": raw_valid,
            "required_count": len(region_ids),
            "missing_or_invalid_region_ids": raw_invalid,
        },
        "artifacts": {
            name: {"count": count, "required_count": len(region_ids)}
            for name, count in artifact_counts.items()
        },
        "embedded_development_artifacts": embedded_counts,
        "stages": stage_status,
    }


def _boundary_status(path: Path, region_ids: tuple[str, ...]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": str(path), "exists": False, "region_count": 0, "missing_region_ids": list(region_ids)}
    found = {
        str((feature.get("properties") or {}).get("region_id") or "").strip()
        for feature in payload.get("features", [])
        if isinstance(feature, dict) and isinstance(feature.get("properties"), dict)
    }
    found.discard("")
    return {
        "path": str(path),
        "exists": True,
        "region_count": len(found),
        "missing_region_ids": sorted(set(region_ids) - found),
    }


def _configured_boundary_path(
    pipeline: dict[str, list[dict[str, Any]]],
    *,
    release_root: Path,
    cache_root: Path,
    base_year_month: str,
) -> Path:
    values = {
        "release_root": str(release_root),
        "cache_root": str(cache_root),
        "repository_root": str(Path.cwd()),
        "python": sys.executable,
        "base_year_month": base_year_month,
    }
    for stage in pipeline.get("global_stages", []):
        if stage.get("name") != "kakao_content":
            continue
        for template in stage.get("inputs", []):
            if str(template).lower().endswith(".geojson"):
                return Path(str(template).format_map(values))
    return Path("data/raw/national_sigungu.geojson")


def _postgresql_database_url() -> bool:
    values = {**_dotenv_values(), **{key: value for key, value in os.environ.items() if value}}
    url = (
        values.get("CONTENT_DATABASE_URL", "").strip()
        or values.get("AUTH_DATABASE_URL", "").strip()
    )
    return url.startswith(("postgresql://", "postgresql+psycopg://"))


def _configured_env_names(dotenv_path: Path = Path(".env")) -> set[str]:
    names = {name for name, value in os.environ.items() if value.strip()}
    names.update(_dotenv_values(dotenv_path))
    return names


def _dotenv_values(dotenv_path: Path = Path(".env")) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        cleaned = value.strip().strip("'\"")
        if separator and key.strip() and cleaned:
            values[key.strip()] = cleaned
    return values


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
