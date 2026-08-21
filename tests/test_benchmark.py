import csv
import json
import tempfile
import unittest
from pathlib import Path

from hankkeut_analysis.benchmark import (
    BenchmarkRegion,
    BenchmarkRegionResult,
    BenchmarkRunReport,
    build_distributions,
    load_benchmark_config,
    validate_tour_region_codes,
)
from hankkeut_analysis.benchmark_output import (
    write_benchmark_anchor_csv,
    write_benchmark_distribution_csv,
)
from hankkeut_analysis.models import HubTouristSpot, TourismResource
from hankkeut_analysis.stay_analysis import analyze_stay_transition


def _region_definition(name):
    return BenchmarkRegion(
        region_name=name,
        province_name="테스트도",
        sample_group="테스트형",
        hub_area_code="47",
        hub_sigungu_code="47130",
        tour_area_code="35",
        tour_sigungu_code="2",
        tour_sigungu_name="테스트시",
    )


def _region_result(name, food_count):
    hub = HubTouristSpot(
        rank=1,
        tourist_spot_code=f"hub-{name}",
        name=f"{name} 관광지",
        category_large="관광지",
        category_middle="역사관광",
        longitude=127.0,
        latitude=37.0,
    )
    resources = [
        TourismResource(
            content_id=f"{name}-food-{index}",
            content_type_id=39,
            longitude=127.0,
            latitude=37.0,
        )
        for index in range(food_count)
    ]
    report = analyze_stay_transition(
        [hub],
        resources,
        region_name=name,
        generated_at="2026-08-04T00:00:00+00:00",
        hub_base_year_month="202503",
        hub_area_code="47",
        hub_sigungu_code="47130",
        tour_area_code="35",
        tour_sigungu_code="2",
        requested_anchor_count=1,
        radii_km=(1.0,),
    )
    return BenchmarkRegionResult(
        definition=_region_definition(name),
        report=report,
    )


class BenchmarkTest(unittest.TestCase):
    def test_loads_config(self) -> None:
        payload = {
            "benchmark_name": "테스트 벤치마크",
            "base_year_month": "202503",
            "anchor_count_per_region": 3,
            "hub_category_large": "관광지",
            "hub_category_middle": "자연관광",
            "output_slug": "test_nature",
            "excluded_hub_category_middle": ["쇼핑"],
            "radii_km": [2, 1, 1],
            "regions": [_region_definition("테스트시").to_dict()],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "benchmark.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            config = load_benchmark_config(path)

        self.assertEqual(config.benchmark_name, "테스트 벤치마크")
        self.assertEqual(config.hub_category_large, "관광지")
        self.assertEqual(config.hub_category_middle, "자연관광")
        self.assertEqual(config.output_slug, "test_nature")
        self.assertEqual(config.excluded_hub_category_middle, ("쇼핑",))
        self.assertEqual(config.radii_km, (1.0, 2.0))
        self.assertEqual(config.regions[0].region_name, "테스트시")

    def test_rejects_middle_category_that_is_also_excluded(self) -> None:
        payload = {
            "benchmark_name": "테스트",
            "base_year_month": "202503",
            "anchor_count_per_region": 2,
            "hub_category_large": "관광지",
            "hub_category_middle": "쇼핑",
            "excluded_hub_category_middle": ["쇼핑"],
            "radii_km": [1],
            "regions": [_region_definition("테스트시").to_dict()],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "benchmark.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "포함될 수 없습니다"):
                load_benchmark_config(path)

    def test_rejects_duplicate_region_names(self) -> None:
        definition = _region_definition("중복시").to_dict()
        payload = {
            "benchmark_name": "테스트",
            "base_year_month": "202503",
            "anchor_count_per_region": 3,
            "hub_category_large": "관광지",
            "excluded_hub_category_middle": ["쇼핑"],
            "radii_km": [1],
            "regions": [definition, definition],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "benchmark.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "중복"):
                load_benchmark_config(path)

    def test_builds_linear_percentiles_and_zero_rate(self) -> None:
        results = tuple(
            _region_result(f"지역{index}", food_count)
            for index, food_count in enumerate((0, 10, 20, 30), start=1)
        )

        distributions = build_distributions(results, radii_km=(1.0,))
        food = next(
            item
            for item in distributions
            if item.grouping_dimension == "sampling_stratum"
            and item.group_name == "테스트형"
            and item.metric_key == "food"
        )

        self.assertEqual(food.sample_count, 4)
        self.assertEqual(food.zero_count, 1)
        self.assertEqual(food.zero_rate_percentage, 25.0)
        self.assertEqual(food.median, 15.0)
        self.assertEqual(food.p75, 22.5)

        category_food = next(
            item
            for item in distributions
            if item.grouping_dimension == "hub_category_middle"
            and item.group_name == "역사관광"
            and item.metric_key == "food"
        )
        self.assertEqual(category_food.sample_count, 4)

    def test_keeps_actual_hub_category_in_stay_report(self) -> None:
        result = _region_result("분류시", 1)
        anchor = result.report.anchors[0]

        self.assertEqual(anchor.category_large, "관광지")
        self.assertEqual(anchor.category_middle, "역사관광")

    def test_validates_official_tour_code_name_and_suggests_code(self) -> None:
        region = _region_definition("테스트시")
        errors = validate_tour_region_codes(
            (region,),
            {"35": {"2": "다른시", "9": "테스트시"}},
        )

        self.assertEqual(len(errors), 1)
        self.assertIn("실제 코드명 '다른시'", errors[0])
        self.assertIn("예상 코드 9", errors[0])

    def test_writes_anchor_and_distribution_csv_with_distinct_group_fields(
        self,
    ) -> None:
        region_result = _region_result("출력시", 1)
        distributions = build_distributions(
            (region_result,),
            radii_km=(1.0,),
        )
        report = BenchmarkRunReport(
            benchmark_name="테스트",
            generated_at="2026-08-04T00:00:00+00:00",
            base_year_month="202503",
            anchor_count_per_region=1,
            hub_category_large="관광지",
            excluded_hub_category_middle=("쇼핑",),
            radii_km=(1.0,),
            region_results=(region_result,),
            distributions=distributions,
            failures=(),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            anchor_path = write_benchmark_anchor_csv(
                report,
                Path(temp_dir) / "anchors.csv",
            )
            distribution_path = write_benchmark_distribution_csv(
                report,
                Path(temp_dir) / "distributions.csv",
            )
            with anchor_path.open(
                encoding="utf-8-sig",
                newline="",
            ) as csv_file:
                anchor_rows = list(csv.DictReader(csv_file))
            with distribution_path.open(
                encoding="utf-8-sig",
                newline="",
            ) as csv_file:
                distribution_rows = list(csv.DictReader(csv_file))

        self.assertEqual(anchor_rows[0]["sample_group"], "테스트형")
        self.assertEqual(
            distribution_rows[0]["grouping_dimension"],
            "overall",
        )
        self.assertEqual(distribution_rows[0]["group_name"], "테스트도 전체")


if __name__ == "__main__":
    unittest.main()
