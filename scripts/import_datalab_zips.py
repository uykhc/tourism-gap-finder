"""Extract DataLab ZIP exports into the region paths from the intake manifest."""

from __future__ import annotations

import argparse
import json
import unicodedata
import zipfile
from pathlib import Path

from datalab_intake_manifest import validate_csv


MAX_CSV_BYTES = 50 * 1024 * 1024


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def import_archives(zip_root: Path, manifest_path: Path, *, overwrite: bool = False) -> int:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        _normalized(str(item["region_name"])): item
        for item in manifest["items"]
    }
    imported = 0

    for archive in sorted(zip_root.glob("*.zip")):
        archive_name = _normalized(archive.stem)
        matches = [name for name in expected if name in archive_name]
        if len(matches) != 1:
            print(f"SKIP {archive.name}: expected region could not be identified")
            continue

        item = expected[matches[0]]
        destination = Path(item["recommended_path"])
        if destination.exists() and not overwrite:
            print(f"SKIP {archive.name}: {destination} already exists")
            continue

        with zipfile.ZipFile(archive) as bundle:
            members = [entry for entry in bundle.infolist() if not entry.is_dir()]
            if len(members) != 1 or not members[0].filename.lower().endswith(".csv"):
                print(f"SKIP {archive.name}: ZIP must contain exactly one CSV")
                continue
            if members[0].file_size > MAX_CSV_BYTES:
                print(f"SKIP {archive.name}: CSV exceeds {MAX_CSV_BYTES} bytes")
                continue
            content = bundle.read(members[0])

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(".csv.tmp")
        temporary.write_bytes(content)
        status, detail = validate_csv(
            temporary,
            expected_region_id=str(item["region_id"]),
        )
        if status != "ready":
            temporary.unlink(missing_ok=True)
            print(f"SKIP {archive.name}: {detail}")
            continue
        temporary.replace(destination)
        imported += 1
        print(f"OK   {archive.name} -> {destination} ({detail})")

    print(f"Imported {imported} archive(s)")
    return imported


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip-root", type=Path, default=Path("data/raw/datalab_navigation")
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/raw/datalab_navigation/intake-manifest.json"),
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    import_archives(args.zip_root, args.manifest, overwrite=args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
