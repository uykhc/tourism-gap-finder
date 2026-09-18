from pathlib import Path
from unittest import mock

from scripts.datalab_intake_manifest import build_manifest, validate_csv


def test_manifest_reports_recommended_path_and_readiness(tmp_path: Path) -> None:
    path = tmp_path / "47130" / "navigation.csv"
    path.parent.mkdir(parents=True)
    path.write_text(
        "기준연월,목적지 유형,목적지 검색량\n202608,관광지,10\n",
        encoding="utf-8",
    )
    with mock.patch(
        "scripts.datalab_intake_manifest.regions.all_regions",
        return_value=[{
            "region_id": "47130",
            "province_name": "경상북도",
            "region_name": "경주시",
        }],
    ):
        payload = build_manifest(tmp_path)

    assert payload["ready_count"] == 1
    assert payload["items"][0]["status"] == "ready"
    recommended_path = Path(payload["items"][0]["recommended_path"])
    assert recommended_path.parts[-2:] == ("47130", "navigation.csv")


def test_invalid_csv_is_not_treated_as_zero(tmp_path: Path) -> None:
    path = tmp_path / "navigation.csv"
    path.write_text("기준연월,목적지 유형\n202608,관광지\n", encoding="utf-8")
    status, _detail = validate_csv(path)
    assert status == "invalid"
