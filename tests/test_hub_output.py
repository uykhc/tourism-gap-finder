import csv
import json
import tempfile
import unittest
from pathlib import Path

from hankkeut_analysis.gap_analyzer.hub_output import write_hub_csv, write_hub_json
from hankkeut_analysis.gap_analyzer.models import HubTouristSpot, HubTouristSpotReport


class HubOutputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.report = HubTouristSpotReport(
            region_name="경주시",
            base_year_month="202503",
            area_code="47",
            sigungu_code="47130",
            limit=5,
            spots=(
                HubTouristSpot(
                    rank=1,
                    tourist_spot_code="A001",
                    name="첫 관광지",
                    category_large="관광자원",
                    longitude=129.1,
                    latitude=35.8,
                    raw_fields={"hubRank": "1"},
                ),
            ),
        )

    def test_writes_json_with_raw_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_hub_json(
                self.report,
                Path(temp_dir) / "nested" / "hubs.json",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["region_name"], "경주시")
        self.assertEqual(payload["extracted_count"], 1)
        self.assertEqual(payload["spots"][0]["name"], "첫 관광지")
        self.assertEqual(payload["spots"][0]["raw_fields"]["hubRank"], "1")

    def test_writes_excel_friendly_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_hub_csv(
                self.report,
                Path(temp_dir) / "hubs.csv",
            )
            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["region_name"], "경주시")
        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(rows[0]["tourist_spot_code"], "A001")


if __name__ == "__main__":
    unittest.main()
