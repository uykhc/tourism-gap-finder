import unittest

from hankkeut_calculation.tourism_data.visitor_api import DailyRegionalVisitor
from hankkeut_evaluation.visitor_portfolio_benchmark import (
    aggregate_daily_visitor_sums,
    build_city_tourism_scores,
)
from hankkeut_calculation.tourism_data.tourism_demand_api import TourismDemandRecord


class VisitorPortfolioBenchmarkTest(unittest.TestCase):
    def test_ranks_only_matching_regions_by_daily_visitor_sum(self) -> None:
        rows, matched = aggregate_daily_visitor_sums(
            [
                DailyRegionalVisitor("20250101", "가평군", 30),
                DailyRegionalVisitor("20250102", "가평군", 20),
                DailyRegionalVisitor("20250101", "수원시", 60),
                DailyRegionalVisitor("20250101", "응답에만 있는 지역", 999),
            ],
            allowed_region_names={"가평군", "수원시"},
        )

        self.assertEqual([row["region_name"] for row in rows], ["수원시", "가평군"])
        self.assertEqual(rows[0]["daily_visitor_sum"], 60)
        self.assertEqual(rows[1]["daily_visitor_sum"], 50)
        self.assertEqual(matched, {"가평군", "수원시"})

    def test_can_filter_visitor_type(self) -> None:
        rows, _ = aggregate_daily_visitor_sums(
            [
                DailyRegionalVisitor("20250101", "수원시", 10, "내국인"),
                DailyRegionalVisitor("20250101", "수원시", 4, "외국인"),
            ],
            allowed_region_names={"수원시"},
            visitor_type_names=("외국인",),
        )

        self.assertEqual(rows[0]["daily_visitor_sum"], 4)

    def test_combines_city_metrics_with_40_30_30_weights(self) -> None:
        record = lambda value: TourismDemandRecord("202512", "1", "테스트", "x", "지표", value)
        scores = build_city_tourism_scores(
            [
                {"region_name": "가시", "daily_visitor_sum": 10},
                {"region_name": "나시", "daily_visitor_sum": 20},
            ],
            {
                "resource_service": {"1": record(10), "2": record(20)},
                "resource_culture": {"1": record(10), "2": record(20)},
                "intensity_stay": {"1": record(20), "2": record(10)},
                "intensity_spend": {"1": record(20), "2": record(10)},
            },
            city_sigungu_codes={"가시": ("1",), "나시": ("2",)},
            visitor_weight=0.4,
            resource_demand_weight=0.3,
            demand_intensity_weight=0.3,
        )

        self.assertEqual([item.region_name for item in scores], ["나시", "가시"])
        self.assertEqual(scores[0].composite_score, 70.0)


if __name__ == "__main__":
    unittest.main()
