import csv
import json
import tempfile
import unittest
from pathlib import Path

from hankkeut_analysis.gap_analyzer.models import HubTouristSpot, TourismResource
from hankkeut_analysis.gap_analyzer.stay_analysis import analyze_stay_transition
from hankkeut_analysis.gap_analyzer.stay_output import (
    write_stay_anchor_csv,
    write_stay_json,
    write_stay_summary_csv,
)


class StayOutputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.report = analyze_stay_transition(
            [
                HubTouristSpot(
                    rank=1,
                    tourist_spot_code="hub-1",
                    name="대표 관광지",
                    longitude=127.0,
                    latitude=37.0,
                )
            ],
            [
                TourismResource(
                    content_id="food-1",
                    content_type_id=39,
                    title="음식점",
                    longitude=127.0,
                    latitude=37.0,
                )
            ],
            region_name="테스트시",
            generated_at="2026-08-04T00:00:00+00:00",
            hub_base_year_month="202503",
            hub_area_code="47",
            hub_sigungu_code="47130",
            tour_area_code="35",
            tour_sigungu_code="2",
        )

    def test_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_stay_json(
                self.report,
                Path(temp_dir) / "nested" / "stay.json",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["region_name"], "테스트시")
        self.assertEqual(payload["analyzed_anchor_count"], 1)
        self.assertEqual(
            payload["anchors"][0]["radii"][0]["complement_coverage_score"],
            20.0,
        )

    def test_writes_anchor_csv_one_row_per_radius(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_stay_anchor_csv(
                self.report,
                Path(temp_dir) / "anchors.csv",
            )
            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "대표 관광지")
        self.assertEqual(rows[0]["food_count"], "1")
        self.assertEqual(rows[0]["complement_coverage_score"], "20.0")

    def test_writes_regional_summary_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_stay_summary_csv(
                self.report,
                Path(temp_dir) / "summary.csv",
            )
            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["average_food_count"], "1.0")
        self.assertEqual(rows[0]["unique_complement_resource_count"], "1")


if __name__ == "__main__":
    unittest.main()
