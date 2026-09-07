import json
import tempfile
import unittest
from pathlib import Path

from hankkeut_calculation.gap_analyzer.analysis import analyze_portfolio
from hankkeut_calculation.gap_analyzer.models import TourismResource
from hankkeut_evaluation.portfolio_benchmark import (
    PortfolioBenchmarkRegion,
    PortfolioBenchmarkRegionResult,
    build_portfolio_distributions,
    load_portfolio_benchmark_config,
    portfolio_region_result_from_dict,
)


def _definition(name: str) -> PortfolioBenchmarkRegion:
    return PortfolioBenchmarkRegion(
        region_name=name,
        province_name="테스트도",
        administrative_type="city",
        area_code="35",
        sigungu_code=name,
        area_square_km=1.0,
    )


def _result(index: int) -> PortfolioBenchmarkRegionResult:
    definition = _definition(str(index))
    resources = [
        TourismResource(content_id=f"spot-{index}-{number}", content_type_id=12)
        for number in range(index)
    ] + [
        TourismResource(content_id=f"food-{index}-{number}", content_type_id=39)
        for number in range(10)
    ]
    report = analyze_portfolio(
        resources,
        region_name=definition.region_name,
        area_code=definition.area_code,
        sigungu_code=definition.sigungu_code,
        area_square_km=definition.area_square_km,
    )
    return PortfolioBenchmarkRegionResult(definition=definition, report=report)


class PortfolioBenchmarkTest(unittest.TestCase):
    def test_loads_config_and_rejects_unknown_administrative_type(self) -> None:
        region = {
            "region_name": "테스트시",
            "province_name": "테스트도",
            "administrative_type": "city",
            "area_code": "35",
            "sigungu_code": "1",
            "area_square_km": 100,
        }
        payload = {
            "benchmark_name": "테스트",
            "output_slug": "test_benchmark",
            "area_reference_date": "2024-12-31",
            "area_source_url": "https://example.com/area",
            "regions": [region],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            config = load_portfolio_benchmark_config(path)
            self.assertEqual(config.regions[0].area_square_km, 100.0)

            payload["regions"][0]["administrative_type"] = "province"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "administrative_type"):
                load_portfolio_benchmark_config(path)

    def test_builds_stratified_distribution(self) -> None:
        results = tuple(_result(index) for index in range(1, 9))
        distributions = build_portfolio_distributions(results)
        tourist_spots = next(
            item
            for item in distributions
            if item.grouping_dimension == "administrative_type"
            and item.group_name == "시"
            and item.content_type_id == 12
        )

        self.assertEqual(tourist_spots.sample_count, 8)
        self.assertEqual(tourist_spots.density_median, 4.5)
        self.assertEqual(tourist_spots.density_p75, 6.25)

    def test_restores_saved_region_result(self) -> None:
        original = _result(3)
        restored = portfolio_region_result_from_dict(original.to_dict())

        self.assertEqual(restored.definition, original.definition)
        self.assertEqual(restored.report, original.report)


if __name__ == "__main__":
    unittest.main()
