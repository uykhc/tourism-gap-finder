"""지역 스냅숏과 기존 관광 API 클라이언트의 HTTP 라우터 연결."""

from __future__ import annotations

import unittest
from unittest import mock

from fastapi import HTTPException

from apps.api.app.routers import analysis, regions
from apps.api.app.services import artifacts


class RegionSnapshotRouteTest(unittest.TestCase):
    def test_region_detail_uses_the_requested_region_snapshot(self) -> None:
        gyeongju = regions.get_region("47130", object())
        jongno = regions.get_region("11110", object())

        self.assertEqual(gyeongju.region_name, "경주시")
        self.assertEqual(jongno.region_name, "종로구")
        self.assertNotEqual(gyeongju.area_km2, jongno.area_km2)
        self.assertNotEqual(gyeongju.total_population, jongno.total_population)

    def test_structure_uses_all_seventeen_values_for_the_requested_region(self) -> None:
        result = regions.get_structure("11110", object())

        self.assertEqual(result.target.region_id, "11110")
        self.assertEqual(result.feature_count, 17)
        self.assertEqual(len(result.features), 17)
        values = {item.feature: item.value for item in result.features}
        self.assertAlmostEqual(values["area_km2"], 23.99606187805176)
        self.assertAlmostEqual(values["total_population"], 151291.0)

    def test_unknown_structure_region_is_404(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            regions.get_structure("99999", object())
        self.assertEqual(caught.exception.status_code, 404)


class LiveAnalysisRouteTest(unittest.TestCase):
    def test_portfolio_reads_the_precomputed_artifact(self) -> None:
        payload = {
            "region_name": "경주시", "area_code": "35", "sigungu_code": "2",
            "area_square_km": 1324.39, "total_resource_count": 1,
            "total_count_per_square_km": 0.0008, "metrics": [],
        }
        with mock.patch.object(artifacts, "portfolio_report", return_value=payload) as loader:
            result = analysis.get_portfolio("47130", object())
        self.assertEqual(result.region_name, "경주시")
        loader.assert_called_once_with("47130")

    def test_hubs_passes_period_and_limit_to_the_artifact_loader(self) -> None:
        payload = {
            "region_name": "경주시", "base_year_month": "202606", "area_code": "35",
            "sigungu_code": "2", "limit": 3, "extracted_count": 1,
            "spots": [{"rank": 1, "tourist_spot_code": "spot-1", "name": "관광지"}],
        }
        with mock.patch.object(artifacts, "hub_report", return_value=payload) as loader:
            result = analysis.get_hubs("47130", object(), base_year_month="202606", limit=3)
        self.assertEqual(result.region_name, "경주시")
        self.assertEqual(result.limit, 3)
        loader.assert_called_once_with("47130", base_year_month="202606", limit=3)


if __name__ == "__main__":
    unittest.main()
