import unittest

from hankkeut_analysis.gap_analyzer.analysis import analyze_portfolio
from hankkeut_analysis.gap_analyzer.models import TourismResource


class AnalyzePortfolioTest(unittest.TestCase):
    def test_calculates_percentage_and_density_and_keeps_zero_types(self) -> None:
        resources = [
            TourismResource("1", 12),
            TourismResource("2", 12),
            TourismResource("3", 39),
            TourismResource("4", 99),
        ]

        report = analyze_portfolio(
            resources,
            region_name="테스트시",
            area_code="1",
            sigungu_code="2",
            area_square_km=2.0,
        )

        metrics = {
            metric.content_type_id: metric for metric in report.metrics
        }
        self.assertEqual(report.total_resource_count, 4)
        self.assertEqual(report.total_count_per_square_km, 2.0)
        self.assertEqual(metrics[12].count, 2)
        self.assertEqual(metrics[12].percentage, 50.0)
        self.assertEqual(metrics[12].count_per_square_km, 1.0)
        self.assertEqual(metrics[14].count, 0)
        self.assertEqual(metrics[14].percentage, 0.0)
        self.assertEqual(metrics[99].content_type_name, "기타(99)")
        self.assertEqual(sum(metric.count for metric in report.metrics), 4)
        self.assertAlmostEqual(
            sum(metric.percentage for metric in report.metrics),
            100.0,
        )

    def test_empty_region_has_eight_zero_metrics(self) -> None:
        report = analyze_portfolio(
            [],
            region_name="빈지역",
            area_code="1",
            sigungu_code="1",
            area_square_km=10.0,
        )

        self.assertEqual(report.total_resource_count, 0)
        self.assertEqual(report.total_count_per_square_km, 0.0)
        self.assertEqual(len(report.metrics), 8)
        self.assertTrue(all(metric.count == 0 for metric in report.metrics))

    def test_unknown_content_type_is_not_dropped(self) -> None:
        report = analyze_portfolio(
            [TourismResource("1", None)],
            region_name="테스트군",
            area_code="1",
            sigungu_code="1",
            area_square_km=5.0,
        )

        unknown = report.metrics[-1]
        self.assertIsNone(unknown.content_type_id)
        self.assertEqual(unknown.content_type_name, "유형 미상")
        self.assertEqual(unknown.count, 1)

    def test_rejects_non_positive_area(self) -> None:
        with self.assertRaises(ValueError):
            analyze_portfolio(
                [],
                region_name="테스트구",
                area_code="1",
                sigungu_code="1",
                area_square_km=0,
            )


if __name__ == "__main__":
    unittest.main()
