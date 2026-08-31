import unittest

from hankkeut_calculation.gap_analyzer.models import HubTouristSpot, TourismResource
from hankkeut_calculation.gap_analyzer.stay_analysis import (
    analyze_stay_transition,
    haversine_distance_km,
)


def _hub(rank, name, longitude=127.0, latitude=37.0):
    return HubTouristSpot(
        rank=rank,
        tourist_spot_code=f"hub-{rank}",
        name=name,
        longitude=longitude,
        latitude=latitude,
    )


def _resource(content_id, content_type_id, longitude=127.0, latitude=37.0):
    return TourismResource(
        content_id=content_id,
        content_type_id=content_type_id,
        title=content_id,
        longitude=longitude,
        latitude=latitude,
    )


def _analyze(hubs, resources, radii=(1.0, 2.0)):
    return analyze_stay_transition(
        hubs,
        resources,
        region_name="테스트시",
        generated_at="2026-08-04T00:00:00+00:00",
        hub_base_year_month="202503",
        hub_area_code="47",
        hub_sigungu_code="47130",
        tour_area_code="35",
        tour_sigungu_code="2",
        requested_anchor_count=5,
        radii_km=radii,
    )


class StayTransitionAnalysisTest(unittest.TestCase):
    def test_counts_five_complement_types_and_calculates_coverage_score(self) -> None:
        resources = [
            _resource("food", 39),
            _resource("stay", 32),
            _resource("culture", 14),
            _resource("event", 15),
            _resource("shopping", 38),
            _resource("tourism", 12),
            _resource("far-food", 39, longitude=128.0),
        ]

        report = _analyze([_hub(1, "대표 관광지")], resources)
        one_km = report.anchors[0].radii[0]
        counts = {count.key: count.count for count in one_km.counts}

        self.assertEqual(counts["food"], 1)
        self.assertEqual(counts["accommodation"], 1)
        self.assertEqual(one_km.total_complement_count, 5)
        self.assertEqual(one_km.covered_type_count, 5)
        self.assertEqual(one_km.complement_coverage_score, 100.0)
        self.assertEqual(one_km.missing_type_names, ())
        self.assertEqual(report.total_tourism_resource_count, 7)
        self.assertEqual(report.geocoded_tourism_resource_count, 7)

    def test_reports_missing_types_without_inflating_score_by_count(self) -> None:
        resources = [
            _resource("food-1", 39),
            _resource("food-2", 39),
            _resource("stay", 32),
        ]

        report = _analyze([_hub(1, "대표 관광지")], resources)
        result = report.anchors[0].radii[0]

        self.assertEqual(result.total_complement_count, 3)
        self.assertEqual(result.complement_coverage_score, 40.0)
        self.assertEqual(
            result.missing_type_names,
            ("문화시설", "행사/공연/축제", "쇼핑"),
        )

    def test_regional_summary_distinguishes_unique_and_overlap_occurrences(self) -> None:
        hubs = [_hub(1, "첫 관광지"), _hub(2, "둘째 관광지")]
        report = _analyze(hubs, [_resource("shared-food", 39)], radii=(1.0,))
        summary = report.regional_summaries[0]

        self.assertEqual(summary.anchor_count, 2)
        self.assertEqual(dict(summary.average_counts)["food"], 1.0)
        self.assertEqual(summary.average_complement_coverage_score, 20.0)
        self.assertEqual(summary.unique_complement_resource_count, 1)
        self.assertEqual(summary.anchor_resource_occurrence_count, 2)
        self.assertEqual(summary.overlap_occurrence_count, 1)

    def test_excludes_resources_without_coordinates(self) -> None:
        resources = [
            _resource("food", 39),
            TourismResource("missing", 32),
        ]

        report = _analyze([_hub(1, "대표 관광지")], resources)

        self.assertEqual(report.total_tourism_resource_count, 2)
        self.assertEqual(report.geocoded_tourism_resource_count, 1)
        self.assertEqual(report.anchors[0].radii[0].total_complement_count, 1)

    def test_haversine_distance_is_about_111_km_per_latitude_degree(self) -> None:
        first = _hub(1, "첫 지점", latitude=37.0)
        second = _resource("second", 39, latitude=38.0)

        distance = haversine_distance_km(first, second)

        self.assertAlmostEqual(distance, 111.2, places=1)

    def test_rejects_hub_without_coordinates(self) -> None:
        hub = HubTouristSpot(1, "hub", "좌표 없음")
        with self.assertRaisesRegex(ValueError, "좌표가 없는"):
            _analyze([hub], [])

    def test_rejects_invalid_radius(self) -> None:
        with self.assertRaisesRegex(ValueError, "분석 반경"):
            _analyze([_hub(1, "대표 관광지")], [], radii=(0,))


if __name__ == "__main__":
    unittest.main()
