"""비교 기준 지역 선정의 세 갈래.

성과가 높은 지역을 찾은 경우, 점수는 나왔지만 대상보다 높은 지역이 없는 경우,
점수를 아예 낼 수 없는 경우는 서로 다른 사실이다. 화면 문구가 그 차이를
그대로 말해야 한다 — 성과 데이터가 있는데 "없어서"라고 쓰면 거짓이 된다.
"""

from __future__ import annotations

import unittest
from unittest import mock

from apps.api.app.services import benchmarks, performance

TARGET = "47130"

RELATIVE_SUPPLY = {
    "peer_regions": [
        {"region_name": "포항시"},
        {"region_name": "서산시"},
    ],
}


class FakeScorer:
    def __init__(self, scores: dict[str, float]) -> None:
        self._scores = scores

    def score(self, region_ids: list[str]) -> dict[str, float]:
        return {key: value for key, value in self._scores.items() if key in region_ids}


class ResolveBenchmarksTest(unittest.TestCase):
    def _resolve(self, scorer):
        with (
            mock.patch.object(performance, "default_scorer", lambda: scorer),
            mock.patch.object(benchmarks.artifacts, "load_performance", return_value=None),
        ):
            return benchmarks.resolve_benchmarks(TARGET, RELATIVE_SUPPLY)

    def test_highest_scoring_peers_become_performance_backed(self):
        selection = self._resolve(FakeScorer({TARGET: 0.10, "47110": 0.90, "44210": 0.50}))
        self.assertTrue(selection.performance_backed)
        self.assertEqual([region["region_id"] for region in selection.regions], ["47110", "44210"])
        self.assertIn("복합점수", selection.rule)

    def test_scored_peers_are_ranked_even_when_target_scores_higher(self):
        selection = self._resolve(FakeScorer({TARGET: 0.99, "47110": 0.10, "44210": 0.20}))
        self.assertTrue(selection.performance_backed)
        self.assertEqual(
            [region["region_id"] for region in selection.regions], ["44210", "47110"]
        )

    def test_no_score_at_all_falls_back_to_the_structural_wording(self):
        selection = self._resolve(performance.UnavailableScorer())
        self.assertFalse(selection.performance_backed)
        self.assertIn("전국 단위로 열리기 전", selection.rule)
        self.assertEqual(len(selection.regions), 2)

    def test_a_missing_key_is_not_an_error(self):
        from fastapi import HTTPException

        class Raising:
            def score(self, region_ids):
                raise HTTPException(503, detail="키 없음")

        selection = self._resolve(Raising())
        self.assertFalse(selection.performance_backed)
        self.assertEqual(len(selection.regions), 2)

    def test_the_scorer_is_consulted_once_per_resolution(self):
        # select_benchmarks가 다시 조회하면 한 요청이 원천 API를 두 번 부른다.
        calls: list[list[str]] = []

        class Counting(FakeScorer):
            def score(self, region_ids):
                calls.append(list(region_ids))
                return super().score(region_ids)

        self._resolve(Counting({TARGET: 0.10, "47110": 0.90}))
        self.assertEqual(len(calls), 1, f"조회가 {len(calls)}번 일어났다")

    def test_precomputed_release_scores_are_used_before_live_api(self):
        values = {TARGET: 10.0, "47110": 90.0, "44210": 5.0}

        def load(region_id: str):
            score = values.get(region_id)
            return None if score is None else {"performance": {"composite_score": score}}

        with (
            mock.patch.object(benchmarks.artifacts, "load_performance", load),
            mock.patch.object(performance, "default_scorer") as live,
        ):
            selection = benchmarks.resolve_benchmarks(TARGET, RELATIVE_SUPPLY)

        self.assertEqual([region["region_id"] for region in selection.regions], ["47110", "44210"])
        self.assertTrue(selection.performance_backed)
        live.assert_not_called()

    def test_without_a_relative_supply_artifact_there_are_no_benchmarks(self):
        selection = benchmarks.resolve_benchmarks(TARGET, None)
        self.assertEqual(selection.regions, ())
        self.assertFalse(selection.performance_backed)

    def test_the_target_is_never_its_own_benchmark(self):
        relative = {"peer_regions": [{"region_name": "경주시"}, {"region_name": "포항시"}]}
        with mock.patch.object(performance, "default_scorer", performance.UnavailableScorer):
            selection = benchmarks.resolve_benchmarks(TARGET, relative)
        self.assertNotIn(TARGET, [region["region_id"] for region in selection.regions])

    def test_keeps_an_id_selected_peer_when_its_name_is_ambiguous(self):
        relative = {
            "peer_regions": [
                {"region_id": "12300", "region_name": "북구"},
                {"region_id": "26230", "region_name": "부산진구"},
                {"region_id": "26260", "region_name": "동래구"},
            ],
        }
        with mock.patch.object(performance, "default_scorer", performance.UnavailableScorer):
            selection = benchmarks.resolve_benchmarks("26350", relative)
        self.assertEqual(
            [region["region_id"] for region in selection.regions],
            ["12300", "26230", "26260"],
        )


if __name__ == "__main__":
    unittest.main()
