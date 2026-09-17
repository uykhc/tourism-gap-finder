from __future__ import annotations

import sys
from pathlib import Path

from scripts.build_api_release import _run_pipeline


def test_pipeline_checkpoints_and_invalidates_when_input_changes(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    release_root = tmp_path / "release"
    raw_csv = raw_root / "47130" / "navigation.csv"
    raw_csv.parent.mkdir(parents=True)
    raw_csv.write_text("기준연월,목적지 유형,목적지 검색량\n202601,관광지,1\n", encoding="utf-8")
    script = (
        "from pathlib import Path; import sys; "
        "p=Path(sys.argv[1]); p.parent.mkdir(parents=True, exist_ok=True); "
        "p.write_text((p.read_text() if p.exists() else '') + 'run\\n')"
    )
    stages = [{
        "name": "source_validation",
        "command": [sys.executable, "-c", script, "{release_root}/marker.txt"],
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
