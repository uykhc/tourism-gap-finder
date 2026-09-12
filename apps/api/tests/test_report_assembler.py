"""보고서 조립 규칙.

빈칸 판정은 산출물이 이미 계산한 두 후보 플래그를 조합한 것이어야 하고,
화면에 나가는 숫자는 어느 것도 LLM 산문에서 뽑아온 값이 아니어야 한다.
"""

from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

from fastapi.testclient import TestClient

from apps.api.app.main import app
from apps.api.app.services import artifacts

SAMPLE_ROOT = Path(artifacts.APP_ROOT) / "data" / "artifacts"
GYEONGJU = "47130"

#: 숫자로 나가야 하는 필드. 문자열로 나가면 프론트가 파싱을 하게 된다.
_NUMERIC_FIELDS = frozenset({
    "value", "composition_share", "supply_density_per_100_km2", "searches_per_place",
    "lowest_benchmark_supply_ratio", "target_to_benchmark_ratio", "benchmark_value",
    "supply_place_count", "navigation_search_count", "lower_benchmark_count",
    "total_benchmark_count", "search_rank", "rank", "total_count", "month_count",
    "total_content_type_count",
})


def _walk(node: Any, path: str = "") -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.append((f"{path}.{key}", key, value))
            found.extend(_walk(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_walk(value, f"{path}[{index}]"))
    return found


class SampleReportTest(unittest.TestCase):
    """커밋된 경주시 샘플 산출물로 조립 결과를 검증한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        response = cls.client.get(f"/regions/{GYEONGJU}/report")
        assert response.status_code == 200, response.text
        cls.report = response.json()
        cls.overview = {item["content_type"]: item for item in cls.report["category_overview"]}

    def test_signal_level_follows_the_two_candidacy_flags(self):
        # 두 신호가 모두 가리키면 STRONG, 한쪽만이면 NEEDS_REVIEW.
        expected = {
            "EXPERIENCE_TOURISM": "STRONG_GAP_CANDIDATE",
            "FOOD": "NEEDS_REVIEW",
            "SHOPPING": "NEEDS_REVIEW",
            "LEISURE_SPORTS": "NEEDS_REVIEW",
            "ACCOMMODATION": "NO_CLEAR_GAP",
            "CULTURE_TOURISM": "NO_CLEAR_GAP",
        }
        self.assertEqual(
            {name: item["signal_level"] for name, item in self.overview.items()}, expected
        )

    def test_every_content_type_appears_exactly_once(self):
        self.assertEqual(len(self.report["category_overview"]), 6)
        self.assertEqual(len(self.overview), 6)

    def test_strong_candidates_come_first_in_the_overview(self):
        order = [item["signal_level"] for item in self.report["category_overview"]]
        rank = {"STRONG_GAP_CANDIDATE": 0, "NEEDS_REVIEW": 1, "NO_CLEAR_GAP": 2}
        self.assertEqual([rank[item] for item in order], sorted(rank[item] for item in order))

    def test_primary_gap_type_is_the_strong_candidate(self):
        self.assertEqual(self.report["summary"]["diagnosis_status"], "GAP_FOUND")
        self.assertEqual(self.report["summary"]["primary_gap_type"], "EXPERIENCE_TOURISM")

    def test_key_metrics_are_two_to_four_entries_with_unique_codes(self):
        metrics = self.report["summary"]["key_metrics"]
        codes = [item["metric_code"] for item in metrics]
        self.assertTrue(2 <= len(metrics) <= 4, f"2~4개여야 한다: {codes}")
        self.assertEqual(len(codes), len(set(codes)))
        for item in metrics:
            self.assertEqual(item["content_type"], "EXPERIENCE_TOURISM")

    def test_minimum_supply_ratio_is_the_lowest_density_ratio_and_names_that_benchmark(self):
        metric = next(
            item for item in self.report["summary"]["key_metrics"]
            if item["metric_code"] == "MIN_BENCHMARK_SUPPLY_RATIO"
        )
        benchmarks = self.report["evidence"]["supply_density"]["benchmarks"]
        ratios = [row["target_to_benchmark_ratio"] for row in benchmarks]
        lowest = min(row for row in ratios if row is not None)
        # 구성비와 밀도를 섞지 않는다. 값은 공급밀도 비율의 최솟값이어야 한다.
        self.assertEqual(metric["value"], lowest)
        argmin = min(
            (row for row in benchmarks if row["target_to_benchmark_ratio"] is not None),
            key=lambda row: row["target_to_benchmark_ratio"],
        )
        self.assertEqual(metric["benchmark_region_id"], argmin["region_id"])
        self.assertEqual(metric["benchmark_region_name"], argmin["region_name"])
        self.assertRegex(metric["benchmark_region_id"], r"^\d{5}$")

    def test_lower_benchmark_count_never_exceeds_the_benchmark_total(self):
        for item in self.report["category_overview"]:
            self.assertLessEqual(item["lower_benchmark_count"], item["total_benchmark_count"])

    def test_search_rank_is_a_permutation_of_one_through_six(self):
        ranks = sorted(item["search_rank"] for item in self.report["category_overview"])
        self.assertEqual(ranks, [1, 2, 3, 4, 5, 6])
        item_ranks = sorted(
            item["rank"] for item in self.report["evidence"]["searches_per_place"]["items"]
        )
        self.assertEqual(item_ranks, [1, 2, 3, 4, 5, 6])

    def test_the_target_is_never_listed_as_its_own_benchmark(self):
        ids = [row["region_id"] for row in self.report["evidence"]["supply_density"]["benchmarks"]]
        self.assertNotIn(GYEONGJU, ids)
        self.assertTrue(ids, "비교 기준 지역이 하나는 있어야 한다")

    def test_quantitative_evidence_is_recomputed_not_taken_from_the_llm(self):
        diagnosis = next(
            item for item in self.report["detailed_diagnoses"]
            if item["content_type"] == "EXPERIENCE_TOURISM"
        )
        density = next(
            item for item in diagnosis["quantitative_evidence"]
            if item["metric_code"] == "SUPPLY_DENSITY_PER_100_KM2"
        )
        self.assertEqual(density["value"], self.overview["EXPERIENCE_TOURISM"]["supply_density_per_100_km2"])
        for comparison in density["comparisons"]:
            self.assertRegex(comparison["region_id"], r"^\d{5}$")

    def test_no_clear_gap_types_are_left_out_of_the_detailed_diagnoses(self):
        diagnosed = {item["content_type"] for item in self.report["detailed_diagnoses"]}
        for name, item in self.overview.items():
            if item["signal_level"] == "NO_CLEAR_GAP":
                self.assertNotIn(name, diagnosed)

    def test_recommended_actions_are_empty_and_the_reason_is_recorded(self):
        self.assertEqual(self.report["recommended_actions"], [])
        self.assertTrue(
            any("실행 제안" in line for line in self.report["methodology"]["limitations"]),
            "생산자가 없다는 사실이 한계 목록에 남아야 한다",
        )

    def test_cases_reference_only_registered_sources(self):
        source_ids = {item["source_id"] for item in self.report["sources"]}
        case_ids = {item["case_id"] for item in self.report["benchmark_cases"]}
        for case in self.report["benchmark_cases"]:
            self.assertTrue(case["source_ids"])
            self.assertLessEqual(set(case["source_ids"]), source_ids)
            # 생산자가 없는 항목은 값을 지어내지 않는다.
            self.assertIsNone(case["case_type"])
            self.assertIsNone(case["period"])
            self.assertIsNone(case["operator"])
        for diagnosis in self.report["detailed_diagnoses"]:
            self.assertLessEqual(set(diagnosis["case_ids"]), case_ids)

    def test_the_report_is_provisional_while_benchmarks_are_structural(self):
        self.assertEqual(self.report["report_status"], "PROVISIONAL")
        self.assertIsNotNone(self.report["methodology"]["provisional_notice"])

    def test_numbers_are_sent_as_numbers_and_missing_values_as_null(self):
        for path, key, value in _walk(self.report):
            # `searches_per_place`처럼 같은 이름이 지표 값으로도, 묶음 객체의
            # 키로도 쓰인다. 잎 노드만 검사한다.
            if key in _NUMERIC_FIELDS and not isinstance(value, (dict, list)):
                self.assertIsInstance(
                    value, (int, float, type(None)),
                    f"{path}가 숫자가 아니다: {value!r}",
                )
                self.assertNotIsInstance(value, str, f"{path}가 문자열로 나갔다")

    def test_no_display_string_is_built_for_the_frontend(self):
        rendered = json.dumps(self.report, ensure_ascii=False)
        for marker in ('"0.70배"', '"2곳 모두"'):
            self.assertNotIn(marker, rendered)


class DataPoorRegionTest(unittest.TestCase):
    def test_a_region_without_artifacts_returns_200_and_insufficient_data(self):
        # 데이터 부족은 HTTP 오류가 아니다. 화면이 상태를 구분해 보여줄 수 있어야 한다.
        response = TestClient(app).get("/regions/41110/report")
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["summary"]["diagnosis_status"], "INSUFFICIENT_DATA")
        self.assertIsNone(report["summary"]["primary_gap_type"])
        self.assertEqual(report["summary"]["key_metrics"], [])
        self.assertEqual(report["summary"]["one_line_review"]["source"], "TEMPLATE")
        for field in ("category_overview", "detailed_diagnoses", "recommended_actions",
                      "benchmark_cases", "sources"):
            self.assertEqual(report[field], [], field)

    def test_only_an_unknown_region_id_is_a_404(self):
        self.assertEqual(TestClient(app).get("/regions/99999/report").status_code, 404)


class EmptyGapTypesTest(unittest.TestCase):
    """AI 스키마에서 `gap_types: []`는 적법하다. 판정 문장을 지어내선 안 된다."""

    def test_an_empty_gap_list_still_returns_a_report(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(SAMPLE_ROOT, root, dirs_exist_ok=True)
            ai_path = next((root / "ai_reports").glob("*.json"))
            payload = json.loads(ai_path.read_text(encoding="utf-8"))
            payload["report"]["gap_types"] = []
            ai_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(artifacts, "ARTIFACT_ROOT", root):
                response = TestClient(app).get(f"/regions/{GYEONGJU}/report")
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["detailed_diagnoses"], [])
        self.assertEqual(report["benchmark_cases"], [])
        # 판정은 산출물 수치에서 나오므로 AI 산문이 없어도 그대로 유지된다.
        self.assertEqual(report["summary"]["primary_gap_type"], "EXPERIENCE_TOURISM")
        self.assertEqual(report["summary"]["one_line_review"]["source"], "TEMPLATE")


class MissingAnalysisPeriodTest(unittest.TestCase):
    def test_a_malformed_analysis_period_fails_loudly(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(SAMPLE_ROOT, root, dirs_exist_ok=True)
            path = next((root / "datalab_navigation").glob("*.json"))
            payload = json.loads(path.read_text(encoding="utf-8"))
            del payload["target_report"]["analysis_period"]
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with mock.patch.object(artifacts, "ARTIFACT_ROOT", root):
                client = TestClient(app, raise_server_exceptions=False)
                response = client.get(f"/regions/{GYEONGJU}/report")
        self.assertEqual(response.status_code, 502)
        self.assertIn("analysis_period", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
