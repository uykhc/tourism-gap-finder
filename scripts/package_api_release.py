"""Package a validated API release for transfer to a persistent artifact volume."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
from pathlib import Path


def package_release(
    artifact_root: Path,
    release_id: str,
    output: Path,
    *,
    required_advanced_count: int = 5,
) -> dict[str, object]:
    release_root = artifact_root / "releases" / release_id
    manifest_path = release_root / "release-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"valid release manifest is required: {manifest_path}") from exc
    if manifest.get("release_id") != release_id or manifest.get("status") != "complete":
        raise ValueError("release manifest is not complete or has a mismatched release_id")
    if manifest.get("complete_count") != 230 or manifest.get("failed_count") != 0:
        raise ValueError("all 230 core region profiles must be complete")
    if int(manifest.get("advanced_report_ready_count") or 0) < required_advanced_count:
        raise ValueError(
            f"advanced reports are incomplete: required={required_advanced_count}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        archive.add(release_root, arcname=f"releases/{release_id}")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    return {
        "release_id": release_id,
        "archive": str(output),
        "sha256": digest,
        "checksum_file": str(checksum_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, default=Path("data/artifacts"))
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--required-advanced-count", type=int, default=5)
    args = parser.parse_args()
    try:
        result = package_release(
            args.artifact_root,
            args.release_id,
            args.output,
            required_advanced_count=args.required_advanced_count,
        )
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
