"""보고서 응답 계약.

프론트엔드와 합의한 필드명·타입이 조용히 바뀌지 않게 고정한다. 필드를
빼거나 이름을 잘못 쓰면 여기서 걸린다.
"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from apps.api.app.main import app

#: 합의된 최상위 필드. 추가·누락·오타를 모두 잡기 위해 정확히 비교한다.
EXPECTED_ROOT_FIELDS = {
    "report_version", "report_status", "generated_at", "target", "analysis_period",
    "summary", "evidence", "category_overview", "detailed_diagnoses",
    "recommended_actions", "benchmark_cases", "methodology", "sources",
}

EXPECTED_CONTENT_TYPES = {
    "FOOD", "ACCOMMODATION", "CULTURE_TOURISM",
    "EXPERIENCE_TOURISM", "LEISURE_SPORTS", "SHOPPING",
}


class ReportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        client = TestClient(app)
        response = client.get("/openapi.json")
        assert response.status_code == 200, response.text
        cls.spec = response.json()
        cls.schemas = cls.spec["components"]["schemas"]

    def test_the_report_response_has_exactly_the_agreed_root_fields(self):
        self.assertEqual(set(self.schemas["RegionReport"]["properties"]), EXPECTED_ROOT_FIELDS)

    def test_content_types_are_the_six_agreed_codes(self):
        self.assertEqual(set(self.schemas["ContentType"]["enum"]), EXPECTED_CONTENT_TYPES)

    def test_the_summary_carries_the_four_agreed_fields(self):
        self.assertEqual(
            set(self.schemas["ReportSummary"]["properties"]),
            {"diagnosis_status", "primary_gap_type", "one_line_review", "key_metrics"},
        )

    def test_key_metrics_are_discriminated_by_metric_code(self):
        key_metrics = self.schemas["ReportSummary"]["properties"]["key_metrics"]
        self.assertEqual(key_metrics["items"]["discriminator"]["propertyName"], "metric_code")
        mapping = set(key_metrics["items"]["discriminator"]["mapping"])
        self.assertEqual(mapping, {
            "MIN_BENCHMARK_SUPPLY_RATIO", "LOWER_BENCHMARK_COUNT", "SEARCHES_PER_PLACE",
            "SUPPLY_PLACE_COUNT", "SUPPLY_DENSITY_PER_100_KM2",
        })

    def test_the_agreed_enum_values_are_unchanged(self):
        expected = {
            "ReportStatus": {"FINAL", "PROVISIONAL"},
            "DiagnosisStatus": {"GAP_FOUND", "NO_CLEAR_GAP", "INSUFFICIENT_DATA"},
            "GapSignalLevel": {"STRONG_GAP_CANDIDATE", "NEEDS_REVIEW", "NO_CLEAR_GAP"},
            "OneLineReviewSource": {"LLM", "TEMPLATE"},
            "BenchmarkCaseType": {"FACILITY", "PROGRAM"},
        }
        for name, values in expected.items():
            self.assertEqual(set(self.schemas[name]["enum"]), values, name)

    def test_administrative_type_keeps_the_values_the_signup_client_already_uses(self):
        # 회원가입 응답이 이미 이 값을 쓰고 프론트 Zod가 의존한다. 세종은
        # '특별자치시'라 스펙의 세 값으로는 표현할 수 없다.
        self.assertEqual(
            set(self.schemas["AdministrativeType"]["enum"]),
            {"시", "군", "자치구", "특별자치시"},
        )

    def test_the_report_path_is_unchanged(self):
        self.assertIn("/regions/{region_id}/report", self.spec["paths"])


if __name__ == "__main__":
    unittest.main()
