from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from scripts.package_api_release import package_release


def test_package_release_requires_all_five_advanced_reports(tmp_path: Path) -> None:
    _manifest(tmp_path, advanced_count=4)
    with pytest.raises(ValueError, match="advanced reports are incomplete"):
        package_release(tmp_path, "launch-202608", tmp_path / "release.tar.gz")


def test_package_release_writes_archive_and_checksum(tmp_path: Path) -> None:
    release_root = _manifest(tmp_path, advanced_count=5)
    (release_root / "payload.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "launch-202608.tar.gz"

    result = package_release(tmp_path, "launch-202608", output)

    assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert output.with_suffix(".gz.sha256").is_file()
    with tarfile.open(output, "r:gz") as archive:
        assert "releases/launch-202608/release-manifest.json" in archive.getnames()


def _manifest(root: Path, *, advanced_count: int) -> Path:
    release_root = root / "releases" / "launch-202608"
    release_root.mkdir(parents=True)
    (release_root / "release-manifest.json").write_text(json.dumps({
        "release_id": "launch-202608",
        "status": "complete",
        "complete_count": 230,
        "failed_count": 0,
        "advanced_report_ready_count": advanced_count,
    }), encoding="utf-8")
    return release_root
