import csv
import json
import tempfile
import unittest
from pathlib import Path

from hankkeut_calculation.gap_analyzer.analysis import analyze_portfolio
from hankkeut_calculation.gap_analyzer.models import TourismResource
from hankkeut_calculation.gap_analyzer.output import write_csv, write_json


class OutputTest(unittest.TestCase):
    def setUp(self) -> None:
        self.report = analyze_portfolio(
            [TourismResource("1", 12), TourismResource("2", 39)],
            region_name="테스트시",
            area_code="1",
            sigungu_code="2",
            area_square_km=4.0,
        )

    def test_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_json(
                self.report,
                Path(temp_dir) / "nested" / "report.json",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["region_name"], "테스트시")
        self.assertEqual(payload["total_resource_count"], 2)
        self.assertEqual(payload["metrics"][0]["content_type_name"], "관광지")

    def test_writes_excel_friendly_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_csv(self.report, Path(temp_dir) / "report.csv")
            with path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))

        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["region_name"], "테스트시")
        self.assertEqual(rows[0]["percentage"], "50.0")


if __name__ == "__main__":
    unittest.main()
