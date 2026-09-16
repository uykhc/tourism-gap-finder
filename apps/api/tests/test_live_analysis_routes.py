"""지역 스냅숏과 기존 관광 API 클라이언트의 HTTP 라우터 연결."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi import HTTPException

from apps.api.app.routers import analysis, regions
from apps.api.app.services import regions as region_table


class RegionSnapshotRouteTest(unittest.TestCase):
    def test_region_detail_uses_the_requested_region_snapshot(self) -> None:
        gyeongju = regions.get_region("47130")
        jongno = regions.get_region("11110")

        self.assertEqual(gyeongju.region_name, "경주시")
        self.assertEqual(jongno.region_name, "종로구")
        self.assertNotEqual(gyeongju.area_km2, jongno.area_km2)
        self.assertNotEqual(gyeongju.total_population, jongno.total_population)

    def test_structure_uses_all_seventeen_values_for_the_requested_region(self) -> None:
        result = regions.get_structure("11110")

        self.assertEqual(result.target.region_id, "11110")
        self.assertEqual(result.feature_count, 17)
        self.assertEqual(len(result.features), 17)
        values = {item.feature: item.value for item in result.features}
        self.assertAlmostEqual(values["area_km2"], 23.99606187805176)
        self.assertAlmostEqual(values["total_population"], 151291.0)

    def test_unknown_structure_region_is_404(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            regions.get_structure("99999")
        self.assertEqual(caught.exception.status_code, 404)


class LiveAnalysisRouteTest(unittest.TestCase):
    def test_portfolio_passes_region_codes_and_snapshot_area_to_existing_logic(self) -> None:
        asked: dict[str, object] = {}

        class FakeClient:
            def __init__(self, key: str) -> None:
                asked["key"] = key

            def fetch_region_resources(self, **kwargs):
                asked.update(kwargs)
                return ["resource"]

        class FakeReport:
            def to_dict(self):
                return {
                    "region_name": "경주시",
                    "area_code": "35",
                    "sigungu_code": "2",
                    "area_square_km": asked["area_square_km"],
                    "total_resource_count": 1,
                    "total_count_per_square_km": 0.0008,
                    "metrics": [],
                }

        def fake_analyze(resources, **kwargs):
            asked["resources"] = resources
            asked.update(kwargs)
            return FakeReport()

        tour_module = SimpleNamespace(TourApiClient=FakeClient, TourApiError=RuntimeError)
        portfolio_module = SimpleNamespace(analyze_portfolio=fake_analyze)

        def require_module(name: str, *, feature: str):
            del feature
            return portfolio_module if name.endswith(".analysis") else tour_module

        with (
            mock.patch.object(analysis.analysis_runtime, "require_env", return_value="key"),
            mock.patch.object(
                analysis.analysis_runtime, "require_module", side_effect=require_module
            ),
        ):
            result = analysis.get_portfolio("47130")

        self.assertEqual(result.region_name, "경주시")
        self.assertEqual(asked["key"], "key")
        self.assertEqual(asked["area_code"], "35")
        self.assertEqual(asked["sigungu_code"], "2")
        expected = region_table.find_region_features("47130")
        self.assertIsNotNone(expected)
        self.assertEqual(asked["area_square_km"], expected["area_km2"])
        self.assertEqual(asked["resources"], ["resource"])

    def test_hubs_passes_query_parameters_and_counts_actual_results(self) -> None:
        asked: dict[str, object] = {}

        class FakeSpot:
            def to_dict(self):
                return {
                    "rank": 1,
                    "tourist_spot_code": "spot-1",
                    "name": "관광지",
                }

        class FakeClient:
            def __init__(self, key: str) -> None:
                asked["key"] = key

            def fetch_top_spots(self, **kwargs):
                asked.update(kwargs)
                return [FakeSpot()]

        hub_module = SimpleNamespace(HubTourApiClient=FakeClient, HubTourApiError=RuntimeError)
        with (
            mock.patch.object(analysis.analysis_runtime, "require_env", return_value="key"),
            mock.patch.object(
                analysis.analysis_runtime, "require_module", return_value=hub_module
            ),
        ):
            result = analysis.get_hubs("47130", base_year_month="202606", limit=3)

        self.assertEqual(result.region_name, "경주시")
        self.assertEqual(result.limit, 3)
        self.assertEqual(result.extracted_count, 1)
        self.assertEqual(len(result.spots), 1)
        self.assertEqual(asked["base_year_month"], "202606")
        self.assertEqual(asked["area_code"], "35")
        self.assertEqual(asked["sigungu_code"], "2")
        self.assertEqual(asked["limit"], 3)

    def test_a_known_region_without_tour_api_codes_is_503(self) -> None:
        with self.assertRaises(HTTPException) as caught:
            analysis.get_portfolio("28125")
        self.assertEqual(caught.exception.status_code, 503)

    def test_a_missing_service_key_is_503(self) -> None:
        unavailable = HTTPException(status_code=503, detail="key missing")
        with (
            mock.patch.object(analysis.analysis_runtime, "require_env", side_effect=unavailable),
            self.assertRaises(HTTPException) as caught,
        ):
            analysis.get_portfolio("47130")
        self.assertEqual(caught.exception.status_code, 503)

    def test_an_upstream_portfolio_error_is_502(self) -> None:
        class UpstreamError(RuntimeError):
            pass

        class BrokenClient:
            def __init__(self, key: str) -> None:
                del key

            def fetch_region_resources(self, **kwargs):
                del kwargs
                raise UpstreamError("upstream failed")

        tour_module = SimpleNamespace(TourApiClient=BrokenClient, TourApiError=UpstreamError)
        portfolio_module = SimpleNamespace(analyze_portfolio=lambda *args, **kwargs: None)

        def require_module(name: str, *, feature: str):
            del feature
            return portfolio_module if name.endswith(".analysis") else tour_module

        with (
            mock.patch.object(analysis.analysis_runtime, "require_env", return_value="key"),
            mock.patch.object(
                analysis.analysis_runtime, "require_module", side_effect=require_module
            ),
            self.assertRaises(HTTPException) as caught,
        ):
            analysis.get_portfolio("47130")
        self.assertEqual(caught.exception.status_code, 502)

    def test_an_upstream_hub_error_is_502(self) -> None:
        class UpstreamError(RuntimeError):
            pass

        class BrokenClient:
            def __init__(self, key: str) -> None:
                del key

            def fetch_top_spots(self, **kwargs):
                del kwargs
                raise UpstreamError("upstream failed")

        hub_module = SimpleNamespace(HubTourApiClient=BrokenClient, HubTourApiError=UpstreamError)
        with (
            mock.patch.object(analysis.analysis_runtime, "require_env", return_value="key"),
            mock.patch.object(
                analysis.analysis_runtime, "require_module", return_value=hub_module
            ),
            self.assertRaises(HTTPException) as caught,
        ):
            analysis.get_hubs("47130", base_year_month="202606", limit=5)
        self.assertEqual(caught.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
