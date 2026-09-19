from __future__ import annotations

import sys
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts.build_api_release import (
    ARTIFACT_DIRECTORIES,
    _activation_error,
    _preflight,
    _run_global_pipeline,
    _run_pipeline,
    _stages_for_region,
)


def test_advanced_activation_gate_rejects_four_and_accepts_five() -> None:
    assert _activation_error(
        status="complete", region_count=230,
        advanced_ready_count=4, require_advanced=True,
    ) == "all five advanced reports must be complete"
    assert _activation_error(
        status="complete", region_count=230,
        advanced_ready_count=5, require_advanced=True,
    ) is None


def test_pipeline_checkpoints_and_invalidates_when_input_changes(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    release_root = tmp_path / "release"
    raw_csv = raw_root / "47130" / "navigation.csv"
    raw_csv.parent.mkdir(parents=True)
    raw_csv.write_text("기준연월,목적지 유형,목적지 검색량\n202601,관광지,1\n", encoding="utf-8")
    kakao_marker = tmp_path / "kakao-marker.json"
    kakao_marker.write_text('{"run_id":"first"}', encoding="utf-8")
    script = (
        "from pathlib import Path; import sys; "
        "p=Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text((p.read_text() if p.exists() else '') + 'run\\n')"
    )
    stages = [{
        "name": "source_validation",
        "command": [sys.executable, "-c", script, "{release_root}/marker.txt"],
        "inputs": [str(raw_root), str(kakao_marker)],
        "outputs": ["marker.txt"],
        "timeout_seconds": 30,
    }]

    first, errors = _run_pipeline(
        region_id="47130", stages=stages, raw_root=raw_root,
        release_root=release_root, cache_root=tmp_path / "cache",
    )
    assert not errors
    assert first[0]["status"] == "complete"
    assert (release_root / "marker.txt").read_text() == "run\n"

    second, errors = _run_pipeline(
        region_id="47130", stages=stages, raw_root=raw_root,
        release_root=release_root, cache_root=tmp_path / "cache",
    )
    assert not errors
    assert second[0]["fingerprint"] == first[0]["fingerprint"]
    assert (release_root / "marker.txt").read_text() == "run\n"

    raw_csv.write_text("기준연월,목적지 유형,목적지 검색량\n202602,관광지,2\n", encoding="utf-8")
    third, errors = _run_pipeline(
        region_id="47130", stages=stages, raw_root=raw_root,
        release_root=release_root, cache_root=tmp_path / "cache",
    )
    assert not errors
    assert third[0]["fingerprint"] != first[0]["fingerprint"]
    assert (release_root / "marker.txt").read_text() == "run\nrun\n"

    kakao_marker.write_text('{"run_id":"second"}', encoding="utf-8")
    fourth, errors = _run_pipeline(
        region_id="47130", stages=stages, raw_root=raw_root,
        release_root=release_root, cache_root=tmp_path / "cache",
    )
    assert not errors
    assert fourth[0]["fingerprint"] != third[0]["fingerprint"]
    assert (release_root / "marker.txt").read_text() == "run\nrun\nrun\n"


def test_advanced_region_stages_only_run_for_the_five_targets() -> None:
    stages = [
        {"name": "portfolio"},
        {"name": "datalab_navigation"},
        {"name": "relative_supply"},
        {"name": "ai_report"},
    ]
    assert [item["name"] for item in _stages_for_region("47130", stages)] == [
        "portfolio", "datalab_navigation", "relative_supply", "ai_report",
    ]
    assert [item["name"] for item in _stages_for_region("41110", stages)] == ["portfolio"]


def test_global_stage_runs_once_and_validates_every_region_output(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    source = tmp_path / "features.csv"
    source.write_text("region_id\n11110\n11140\n", encoding="utf-8")
    script = (
        "from pathlib import Path; import sys; "
        "root=Path(sys.argv[1]); root.mkdir(parents=True, exist_ok=True); "
        "[(root / f'{{rid}}.json').write_text('{{}}') for rid in ('11110','11140')]; "
        "marker=Path(sys.argv[2]); marker.write_text((marker.read_text() if marker.exists() else '')+'run\\n')"
    )
    stages = [{
        "name": "peer_candidates",
        "command": [sys.executable, "-c", script, "{release_root}/peer_candidates", "{release_root}/runs.txt"],
        "inputs": [str(source)],
        "outputs": ["peer_candidates/{region_id}.json"],
        "timeout_seconds": 30,
    }]

    with mock.patch(
        "scripts.build_api_release.regions.all_region_ids",
        return_value=["11110", "11140"],
    ):
        first, errors = _run_global_pipeline(
            stages=stages, release_root=release_root, cache_root=tmp_path / "cache"
        )
        second, second_errors = _run_global_pipeline(
            stages=stages, release_root=release_root, cache_root=tmp_path / "cache"
        )

    assert not errors
    assert not second_errors
    assert first[0]["status"] == "complete"
    assert second[0]["fingerprint"] == first[0]["fingerprint"]
    assert (release_root / "runs.txt").read_text() == "run\n"


def test_preflight_reports_counts_without_secret_values(tmp_path: Path, monkeypatch) -> None:
    raw_root = tmp_path / "raw"
    release_root = tmp_path / "release"
    raw_csv = raw_root / "11110" / "navigation.csv"
    raw_csv.parent.mkdir(parents=True)
    raw_csv.write_text("기준연월,목적지 유형,목적지 검색량\n202601,관광지,1\n", encoding="utf-8")
    for directory in ARTIFACT_DIRECTORIES:
        path = release_root / directory / "11110.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leak")

    with mock.patch(
        "scripts.build_api_release.regions.all_region_ids",
        return_value=["11110", "11140"],
    ):
        result = _preflight(
            raw_root=raw_root,
            release_root=release_root,
            pipeline={"global_stages": [], "region_stages": []},
        )

    assert result["ready"] is False
    assert result["credentials"]["openai"] is True
    assert result["raw_navigation"]["valid_count"] == 1
    assert result["artifacts"][ARTIFACT_DIRECTORIES[0]]["count"] == 1
    assert "must-not-leak" not in str(result)


def test_preflight_rejects_a_database_run_changed_after_marker(
    tmp_path: Path, monkeypatch
) -> None:
    raw_root = tmp_path / "raw"
    release_root = tmp_path / "release"
    raw_csv = raw_root / "11110" / "navigation.csv"
    raw_csv.parent.mkdir(parents=True)
    raw_csv.write_text("카테고리중분류명,유형별 검색건수\n음식,1\n", encoding="utf-8")
    for directory in ARTIFACT_DIRECTORIES:
        path = release_root / directory / "11110.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    marker = release_root / "source-markers" / "kakao-content.json"
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        "run_id": "run-1", "normalized_sha256": "original",
    }), encoding="utf-8")
    monkeypatch.setenv("CONTENT_DATABASE_URL", "postgresql://example")

    class FakeProvider:
        def __init__(self, *_args, **_kwargs):
            self.run = SimpleNamespace(
                run_id="run-1", taxonomy_version="v1",
                normalized_sha256="changed", regions={"11110": {}},
            )

    with (
        mock.patch("scripts.build_api_release.regions.all_region_ids", return_value=["11110"]),
        mock.patch(
            "hankkeut_calculation.datalab_navigation.kakao_supply.PostgresKakaoSupplyProvider",
            FakeProvider,
        ),
    ):
        result = _preflight(
            raw_root=raw_root,
            release_root=release_root,
            pipeline={"global_stages": [], "region_stages": []},
            kakao_run_id="run-1",
            require_advanced=True,
        )

    assert result["ready"] is False
    assert result["kakao_database"]["valid"] is False
    assert "변경" in result["kakao_database"]["error"]


def test_missing_prerequisite_blocks_stage_without_running_command(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    marker = release_root / "must-not-exist.txt"
    stages = [{
        "name": "needs_source",
        "command": [sys.executable, "-c", "from pathlib import Path; Path(r'%s').write_text('ran')" % marker],
        "inputs": [str(tmp_path / "missing-source.json")],
        "outputs": ["result.json"],
        "timeout_seconds": 30,
    }]

    records, errors = _run_global_pipeline(
        stages=stages,
        release_root=release_root,
        cache_root=tmp_path / "cache",
    )

    assert errors == ["stage needs_source: blocked by missing prerequisites"]
    assert records[0]["status"] == "blocked"
    assert records[0]["missing_inputs"] == [str(tmp_path / "missing-source.json")]
    assert not marker.exists()


def test_missing_required_value_blocks_stage(tmp_path: Path) -> None:
    stages = [{
        "name": "hubs",
        "command": [sys.executable, "-c", "raise SystemExit('must not run')"],
        "outputs": ["hubs/47130.json"],
        "requires_values": ["base_year_month"],
        "timeout_seconds": 30,
    }]

    records, errors = _run_global_pipeline(
        stages=stages,
        release_root=tmp_path / "release",
        cache_root=tmp_path / "cache",
    )

    assert errors == ["stage hubs: blocked by missing prerequisites"]
    assert records[0]["status"] == "blocked"
    assert records[0]["missing_values"] == ["base_year_month"]


def test_sqlite_does_not_satisfy_content_database_requirement(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CONTENT_DATABASE_URL", raising=False)
    monkeypatch.setenv("AUTH_DATABASE_URL", "sqlite:///local.db")
    stages = [{
        "name": "kakao_content",
        "command": [sys.executable, "-c", "raise SystemExit('must not run')"],
        "outputs": ["marker.json"],
        "requires_postgresql_database": True,
        "timeout_seconds": 30,
    }]

    records, errors = _run_global_pipeline(
        stages=stages,
        release_root=tmp_path / "release",
        cache_root=tmp_path / "cache",
    )

    assert errors == ["stage kakao_content: blocked by missing prerequisites"]
    assert records[0]["status"] == "blocked"
    assert records[0]["missing_values"] == ["postgresql_content_database"]


def test_blocked_stage_does_not_prevent_independent_later_stage(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    script = (
        "from pathlib import Path; import sys; "
        "p=Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True); p.write_text('ok')"
    )
    stages = [
        {
            "name": "blocked",
            "command": [sys.executable, "-c", "raise SystemExit('must not run')"],
            "inputs": [str(tmp_path / "missing")],
            "outputs": ["blocked.json"],
            "timeout_seconds": 30,
        },
        {
            "name": "independent",
            "command": [sys.executable, "-c", script, "{release_root}/independent.json"],
            "outputs": ["independent.json"],
            "timeout_seconds": 30,
        },
    ]

    records, errors = _run_global_pipeline(
        stages=stages,
        release_root=release_root,
        cache_root=tmp_path / "cache",
    )

    assert errors == ["stage blocked: blocked by missing prerequisites"]
    assert [record["status"] for record in records] == ["blocked", "complete"]
    assert (release_root / "independent.json").read_text() == "ok"
