from pathlib import Path
from unittest import mock

from scripts.datalab_intake_manifest import build_manifest, validate_csv


def test_manifest_reports_recommended_path_and_readiness(tmp_path: Path) -> None:
    path = tmp_path / "47130" / "navigation.csv"
    path.parent.mkdir(parents=True)
    rows = "".join(f"{month},관광지,10\n" for month in (
        "202509", "202510", "202511", "202512", "202601", "202602",
        "202603", "202604", "202605", "202606", "202607", "202608",
    ))
    path.write_text("기준연월,목적지 유형,목적지 검색량\n" + rows, encoding="utf-8")
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


def test_csv_requires_the_exact_twelve_month_window(tmp_path: Path) -> None:
    path = tmp_path / "navigation.csv"
    path.write_text(
        "기준연월,목적지 유형,목적지 검색량\n202509,관광지,10\n",
        encoding="utf-8",
    )
    status, detail = validate_csv(path)
    assert status == "invalid"
    assert "analysis period mismatch" in detail


def test_period_total_export_matches_the_supported_download_format(tmp_path: Path) -> None:
    path = tmp_path / "navigation.csv"
    path.write_text(
        "﻿카테고리중분류명,유형별 검색건수,유형별 검색건수 비율,\n"
        "자연관광,74493,0.6,2\n역사관광,292718,2.4,3\n실수,1,0,0\n",
        encoding="utf-8",
    )
    status, detail = validate_csv(path)
    assert status == "invalid"
    assert "destination type mismatch" in detail

    path.write_text(
        "﻿카테고리중분류명,유형별 검색건수,유형별 검색건수 비율,\n"
        "자연관광,74493,0.6,2\n역사관광,292718,2.4,3\n"
        "체험관광,174105,1.4,4\n문화관광,1639491,13.5,5\n"
        "레저스포츠,249638,2.1,6\n쇼핑,3168093,26.1,7\n"
        "음식,5575024,45.9,8\n숙박,599190,4.9,9\n기타관광,382016,3.1,99\n",
        encoding="utf-8",
    )
    status, detail = validate_csv(path)
    assert status == "ready"
    assert "period total (202509~202608)" in detail
