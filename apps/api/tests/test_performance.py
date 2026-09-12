"""우수 지역 선정.

`COLLABORATION.md` §8이 정한 네 가지 보장을 그대로 확인한다. 가짜 scorer만
쓰므로 키도 네트워크도 필요 없다.
"""

from __future__ import annotations

import unittest

from apps.api.app.services import performance
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


class RegionCodeFilterTest(unittest.TestCase):
    def test_regions_without_a_tour_api_code_are_excluded(self):
        # 제물포구(28125)는 2026년 개편 신설로 TourAPI 코드가 없다.
        coded = performance._regions_with_codes(["47130", "28125", "47110"])
        self.assertEqual(sorted(coded), ["47110", "47130"])

    def test_same_named_regions_in_one_group_are_both_excluded(self):
        # 방문자 API는 지역명으로만 조인된다. 같은 집단에 중구가 둘이면
        # 어느 쪽 값인지 알 수 없다.
        coded = performance._regions_with_codes(["11140", "26110", "47130"])
        self.assertEqual(sorted(coded), ["47130"])

    def test_an_unknown_region_is_skipped(self):
        self.assertEqual(performance._regions_with_codes(["99999"]), {})


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
