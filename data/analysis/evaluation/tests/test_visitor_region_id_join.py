"""방문자 집계와 성과 점수를 지역명이 아니라 region_id로 조인한다.

중구는 5곳, 서구·남구·북구는 4곳이다. 지역명으로 묶으면 서로 다른 지역의
방문자 수가 한 덩어리로 합산되고, 그 합으로 낸 백분위가 성과 점수가 된다.
"""

import unittest
from dataclasses import dataclass

from hankkeut_calculation.tourism_data.visitor_api import DailyRegionalVisitor
from hankkeut_evaluation.visitor_portfolio_benchmark import (
    aggregate_daily_visitor_sums,
    build_regional_tourism_scores,
)


@dataclass(frozen=True)
class FakeRecord:
    value: float


def _records():
    return [
        DailyRegionalVisitor("20260701", "중구", 100.0, "현지인(a)", "11140"),   # 서울 중구
        DailyRegionalVisitor("20260701", "중구", 7.0, "현지인(a)", "26110"),     # 부산 중구
        DailyRegionalVisitor("20260701", "종로구", 50.0, "현지인(a)", "11110"),
    ]


class AggregateByRegionIdTest(unittest.TestCase):
    def test_same_named_regions_stay_separate(self):
        rows, seen = aggregate_daily_visitor_sums(
            _records(), allowed_region_ids={"11140", "26110", "11110"}
        )
        sums = {row["region_id"]: row["daily_visitor_sum"] for row in rows}
        self.assertEqual(sums, {"11140": 100.0, "26110": 7.0, "11110": 50.0})
        self.assertEqual(seen, {"11140", "26110", "11110"})

    def test_grouping_by_name_merges_them_which_is_the_bug_being_avoided(self):
        rows, _ = aggregate_daily_visitor_sums(
            _records(), allowed_region_names={"중구", "종로구"}
        )
        sums = {row["region_name"]: row["daily_visitor_sum"] for row in rows}
        self.assertEqual(sums["중구"], 107.0, "이름으로 묶으면 두 중구가 합쳐진다")

    def test_rows_keyed_by_id_still_carry_the_display_name(self):
        rows, _ = aggregate_daily_visitor_sums(_records(), allowed_region_ids={"26110"})
        self.assertEqual(rows[0]["region_name"], "중구")
        self.assertEqual(rows[0]["region_id"], "26110")

    def test_records_without_a_code_are_skipped_when_grouping_by_id(self):
        records = [DailyRegionalVisitor("20260701", "종로구", 50.0, "현지인(a)", "")]
        rows, seen = aggregate_daily_visitor_sums(records, allowed_region_ids={"11110"})
        self.assertEqual(rows, [])
        self.assertEqual(seen, set())

    def test_exactly_one_filter_must_be_given(self):
        with self.assertRaises(ValueError):
            aggregate_daily_visitor_sums(_records())
        with self.assertRaises(ValueError):
            aggregate_daily_visitor_sums(
                _records(), allowed_region_names={"중구"}, allowed_region_ids={"11140"}
            )


class ScoreJoinKeyTest(unittest.TestCase):
    def _demand(self, codes):
        return {
            metric: {code: FakeRecord(float(index + 1) * 10) for index, code in enumerate(codes)}
            for metric in ("resource_service", "resource_culture", "intensity_stay", "intensity_spend")
        }

    def test_scores_join_on_region_id_when_rows_carry_it(self):
        rows, _ = aggregate_daily_visitor_sums(
            _records(), allowed_region_ids={"11140", "26110"}
        )
        scores = build_regional_tourism_scores(
            rows,
            self._demand(["11:11140", "26:26110"]),
            region_sigungu_codes={"11140": ("11:11140",), "26110": ("26:26110",)},
            visitor_weight=0.4, resource_demand_weight=0.3, demand_intensity_weight=0.3,
        )
        by_id = {item.region_id: item for item in scores}
        self.assertEqual(set(by_id), {"11140", "26110"})
        # 표시용 이름은 그대로 남는다.
        self.assertEqual(by_id["11140"].region_name, "중구")
        self.assertEqual(by_id["26110"].region_name, "중구")
        # 서울 중구가 방문자 수 100, 부산 중구가 7이므로 백분위가 갈린다.
        self.assertGreater(by_id["11140"].visitor_percentile, by_id["26110"].visitor_percentile)

    def test_the_name_keyed_path_still_works(self):
        rows, _ = aggregate_daily_visitor_sums(
            _records(), allowed_region_names={"중구", "종로구"}
        )
        scores = build_regional_tourism_scores(
            rows,
            self._demand(["11:11140", "11:11110"]),
            region_sigungu_codes={"중구": ("11:11140",), "종로구": ("11:11110",)},
            visitor_weight=0.4, resource_demand_weight=0.3, demand_intensity_weight=0.3,
        )
        self.assertEqual({item.region_name for item in scores}, {"중구", "종로구"})
        self.assertEqual({item.region_id for item in scores}, {""})

    def test_a_region_without_visitor_data_is_refused_loudly(self):
        rows, _ = aggregate_daily_visitor_sums(_records(), allowed_region_ids={"11140"})
        with self.assertRaisesRegex(ValueError, "26110"):
            build_regional_tourism_scores(
                rows,
                self._demand(["11:11140", "26:26110"]),
                region_sigungu_codes={"11140": ("11:11140",), "26110": ("26:26110",)},
                visitor_weight=0.4, resource_demand_weight=0.3, demand_intensity_weight=0.3,
            )


if __name__ == "__main__":
    unittest.main()
