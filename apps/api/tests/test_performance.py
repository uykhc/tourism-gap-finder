"""우수 지역 선정.

`COLLABORATION.md` §8이 정한 네 가지 보장을 그대로 확인한다. 가짜 scorer만
쓰므로 키도 네트워크도 필요 없다.
"""

from __future__ import annotations

import unittest

from apps.api.app.services import performance
from apps.api.app.services import regions as region_table
from apps.api.app.services.performance import (
    UnavailableScorer,
    select_benchmarks,
)

TARGET = "47130"
PEERS = ["47110", "44210", "44270", "52130"]


class FakeScorer:
    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores
        self.asked: list[list[str]] = []

    def score(self, region_ids: list[str]) -> dict[str, float]:
        self.asked.append(list(region_ids))
        return {key: value for key, value in self._scores.items() if key in region_ids}


class SelectBenchmarksTest(unittest.TestCase):
    def test_returns_only_peers_with_a_higher_score(self):
        scorer = FakeScorer({TARGET: 0.50, "47110": 0.81, "44210": 0.60, "44270": 0.40})
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=scorer), ["47110", "44210"])

    def test_never_returns_a_region_outside_the_peer_list(self):
        scorer = FakeScorer({TARGET: 0.10, "47110": 0.90, "11680": 0.99})
        result = select_benchmarks(TARGET, ["47110"], scorer=scorer)
        self.assertEqual(result, ["47110"])
        self.assertNotIn("11680", result)

    def test_never_returns_the_target_itself(self):
        scorer = FakeScorer({TARGET: 0.90, "47110": 0.95})
        result = select_benchmarks(TARGET, [TARGET, "47110"], scorer=scorer)
        self.assertNotIn(TARGET, result)
        self.assertEqual(result, ["47110"])

    def test_a_tie_is_not_evidence_of_being_better(self):
        scorer = FakeScorer({TARGET: 0.70, "47110": 0.70})
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=scorer), [])

    def test_an_unscored_peer_is_dropped_rather_than_treated_as_zero(self):
        # 결측을 0으로 보면 '성과 바닥'이 되어 순위가 뒤집힌다.
        scorer = FakeScorer({TARGET: 0.50, "47110": 0.80})
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=scorer), ["47110"])

    def test_no_target_score_means_no_benchmarks(self):
        scorer = FakeScorer({"47110": 0.99, "44210": 0.98})
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=scorer), [])

    def test_an_empty_result_is_a_normal_outcome(self):
        scorer = FakeScorer({TARGET: 0.99, "47110": 0.10, "44210": 0.20})
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=scorer), [])

    def test_the_count_limit_is_honoured_and_ordered_by_score(self):
        scorer = FakeScorer({
            TARGET: 0.10, "47110": 0.40, "44210": 0.90, "44270": 0.70, "52130": 0.50,
        })
        self.assertEqual(
            select_benchmarks(TARGET, PEERS, scorer=scorer), ["44210", "44270", "52130"]
        )
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=scorer, k=1), ["44210"])

    def test_a_variable_peer_count_is_fine(self):
        scorer = FakeScorer({TARGET: 0.10, "47110": 0.90})
        self.assertEqual(select_benchmarks(TARGET, [], scorer=scorer), [])
        self.assertEqual(select_benchmarks(TARGET, ["47110"], scorer=scorer), ["47110"])

    def test_the_scorer_is_asked_about_the_target_and_its_peers_together(self):
        # 백분위는 비교 집단 안에서만 의미가 있다.
        scorer = FakeScorer({TARGET: 0.5})
        select_benchmarks(TARGET, ["47110", "44210"], scorer=scorer)
        self.assertEqual(scorer.asked, [[TARGET, "47110", "44210"]])

    def test_without_scores_nothing_is_selected(self):
        self.assertEqual(select_benchmarks(TARGET, PEERS, scorer=UnavailableScorer()), [])


class DemandCodeLookupTest(unittest.TestCase):
    """수요지수 API는 법정동 코드로 조회한다. TourAPI 코드와 다른 체계다."""

    def test_a_plain_city_maps_to_its_own_code(self):
        self.assertEqual(performance._regions_with_codes(["47130"]), {"47130": ("47:47130",)})

    def test_a_city_with_general_districts_maps_to_every_district(self):
        # 수요지수 API는 수원시(41110)를 공표하지 않고 4개 구만 공표한다.
        coded = performance._regions_with_codes(["41110"])
        self.assertEqual(coded["41110"], ("41:41111", "41:41113", "41:41115", "41:41117"))

    def test_a_reorganized_region_maps_to_its_pre_reorganization_code(self):
        # 순천시는 우리 표에서 12150이지만 API는 아직 46150으로 공표한다.
        # 뒤 3자리를 전남에 붙이면 46770(고흥군)이 나오므로 그렇게 만들지 않는다.
        self.assertEqual(performance._regions_with_codes(["12150"]), {"12150": ("46:46150",)})
        self.assertEqual(performance._regions_with_codes(["12770"]), {"12770": ("46:46800",)})

    def test_same_named_regions_are_both_kept(self):
        # 조인이 region_id로 이뤄지므로 서울 중구와 부산 중구는 다른 키다.
        coded = performance._regions_with_codes(["11140", "26110"])
        self.assertEqual(sorted(coded), ["11140", "26110"])
        self.assertNotEqual(coded["11140"], coded["26110"])

    def test_an_unknown_region_is_skipped(self):
        self.assertEqual(performance._regions_with_codes(["99999"]), {})

    def test_the_tour_api_map_is_a_separate_code_system(self):
        # 두 표를 섞어 쓰면 조회가 조용히 실패한다. 경주시는 TourAPI 35/2,
        # 수요지수 47130이다.
        self.assertEqual(region_table.tour_api_code("47130"), ("35", "2"))
        self.assertEqual(region_table.demand_codes("47130"), ("47130",))


class VisitorTotalTest(unittest.TestCase):
    def test_the_direct_code_is_used_when_present(self):
        total = performance._visitor_total("12150", ("46:46150",), {"12150": 5.0, "46150": 9.0})
        self.assertEqual(total, 5.0)

    def test_the_pre_reorganization_code_is_the_fallback(self):
        # 개편이 반영되지 않은 달에는 광주·전남이 옛 코드로만 공표된다.
        total = performance._visitor_total("12150", ("46:46150",), {"46150": 9.0})
        self.assertEqual(total, 9.0)

    def test_a_city_with_general_districts_is_not_summed_from_its_districts(self):
        # 시 단위 행이 따로 있으므로 구 값을 더해 시를 만들지 않는다.
        total = performance._visitor_total(
            "41110", ("41:41111", "41:41113"), {"41111": 1.0, "41113": 2.0}
        )
        self.assertIsNone(total)

    def test_a_region_with_no_visitor_row_yields_nothing(self):
        self.assertIsNone(performance._visitor_total("47130", ("47:47130",), {}))


class LegacyCodeTest(unittest.TestCase):
    def test_only_reorganized_regions_contribute_legacy_codes(self):
        legacy = region_table.legacy_region_codes()
        # 광주 5 + 전남 22 = 27곳이 개편으로 코드가 바뀌었다.
        self.assertEqual(len(legacy), 27)
        self.assertIn("46150", legacy)
        # 일반구 코드는 개편과 무관하므로 들어오지 않는다.
        self.assertNotIn("41111", legacy)
        # 우리 표의 코드가 그대로인 지역도 들어오지 않는다.
        self.assertNotIn("47130", legacy)


class ScorerCacheTest(unittest.TestCase):
    """방문자 조회는 한 달치 전국 데이터(하루 약 800행)다.

    리포트 엔드포인트가 요청마다 이걸 다시 받으면 한 번의 요청이 원천 API
    수십 호출이 된다. 기준월이 같으면 한 번만 받아야 한다.
    """

    def test_a_second_call_for_the_same_month_does_not_refetch(self):
        from types import SimpleNamespace
        from unittest import mock

        from hankkeut_calculation.tourism_data.visitor_api import DailyRegionalVisitor

        performance.VisitorScorer.clear_caches()
        self.addCleanup(performance.VisitorScorer.clear_caches)
        fetches: list[str] = []

        class FakeVisitorClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def fetch_local_daily_visitors(self, *, start_ymd, end_ymd):
                fetches.append(start_ymd)
                return [
                    DailyRegionalVisitor("20260701", "경주시", 10.0, "현지인(a)", "47130"),
                    DailyRegionalVisitor("20260701", "포항시", 20.0, "현지인(a)", "47110"),
                ]

        real_require = performance.require_module

        def fake_require(name, *, feature):
            if name.endswith("visitor_api"):
                return SimpleNamespace(VisitorApiClient=FakeVisitorClient)
            return real_require(name, feature=feature)

        scorer = performance.VisitorScorer()
        with mock.patch.object(performance, "require_module", fake_require):
            first = scorer._visitor_sums("key", "202607")
            second = scorer._visitor_sums("key", "202607")
            other_month = scorer._visitor_sums("key", "202606")

        self.assertEqual(first, {"47130": 10.0, "47110": 20.0})
        self.assertEqual(second, first)
        self.assertEqual(fetches, ["20260701", "20260601"], "같은 달은 한 번만 받아야 한다")
        self.assertEqual(other_month, first)


class DefaultScorerTest(unittest.TestCase):
    def test_without_a_key_the_scorer_reports_no_scores(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"VISITOR_API_SERVICE_KEY": "", "TOUR_API_SERVICE_KEY": ""}):
            scorer = performance.default_scorer()
        self.assertIsInstance(scorer, UnavailableScorer)
        self.assertEqual(scorer.score([TARGET]), {})


if __name__ == "__main__":
    unittest.main()
