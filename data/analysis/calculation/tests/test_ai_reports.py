import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from hankkeut_calculation.ai_reports.case_search import (
    CaseSearchDocument,
    SourceKind,
    build_case_search_queries,
    screen_case_documents,
)
from hankkeut_calculation.ai_reports.report_schema import validate_report_payload
from hankkeut_calculation.ai_reports.openai_report import (
    DEFAULT_MAX_PEER_REGIONS,
    DEFAULT_MODEL,
    OpenAITourismReportGenerator,
    _brief_case_evidence,
    _publication_date,
    _prepare_context,
    collect_approved_case_sources,
    resolve_openai_api_key,
)


class CaseSearchTest(unittest.TestCase):
    def test_builds_peer_queries_and_screens_attributable_sources(self):
        queries = build_case_search_queries(content_type="EXPERIENCE_TOURISM", peer_regions=["강릉시", "강릉시", "전주시"])
        self.assertEqual([query.peer_region for query in queries], ["강릉시", "전주시"])
        self.assertIn("체험관광", queries[0].query)
        sources = screen_case_documents([
            CaseSearchDocument("공식 사례", "https://city.example/case", "강릉시", SourceKind.LOCAL_GOVERNMENT, "방문객 10만 명을 기록했다.", "2026-01-01"),
            CaseSearchDocument("제외", "http://news.example/case", "언론", SourceKind.NEWS, "근거"),
        ])
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_id, "source-1")

    def test_bounds_case_evidence_before_it_is_sent_to_the_report_model(self):
        brief = _brief_case_evidence("가 " * 200)
        self.assertLessEqual(len(brief), 240)
        self.assertTrue(brief.endswith("…"))

    def test_accepts_only_an_explicit_web_source_publication_date(self):
        self.assertEqual(_publication_date("PUBLISHED_AT: 2026-01-31\n근거"), "2026-01-31")
        self.assertEqual(_publication_date("PUBLISHED_AT: 2024\n근거"), "2024")
        self.assertIsNone(_publication_date("행사는 2026년에 열렸다."))
        self.assertIsNone(_publication_date("PUBLISHED_AT: UNKNOWN"))


class ReportSchemaTest(unittest.TestCase):
    def test_accepts_valid_payload_and_rejects_unknown_case_source(self):
        payload = _payload()
        validate_report_payload(payload)
        payload["gap_types"][0]["peer_cases"][0]["source_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "등록된 source_id"):
            validate_report_payload(payload)

    def test_accepts_an_empty_gap_list_when_no_type_meets_the_rule(self):
        payload = _payload()
        payload["gap_types"] = []
        validate_report_payload(payload)


class OpenAIReportGeneratorTest(unittest.TestCase):
    def test_uses_luna_structured_output_and_validates_input_evidence(self):
        response = _FakeResponse(_payload())
        generator = OpenAITourismReportGenerator(
            _FakeClient(response), schema_path=Path("config/ai/tourism_gap_report.schema.json"),
        )
        source = screen_case_documents([
            CaseSearchDocument("공식 문서", "https://city.example/case", "강릉시", SourceKind.LOCAL_GOVERNMENT, "성과", "2026-01-01"),
        ])[0]
        result = generator.generate(
            ai_report_context={
                "region_name": "수원시", "analysis_period": "202509~202608",
                "metric_definition": "검색량 ÷ 장소 수", "limitation": "단일 지역 파일럿",
                "priority_order_by_supply_pressure": ["CULTURE_TOURISM"],
                "content_type_metrics": [{"content_type": "CULTURE_TOURISM", "searches_per_place": 8516.021}],
            },
            peer_regions=["강릉시"],
            approved_sources=[source],
        )
        self.assertEqual(result.model, DEFAULT_MODEL)
        self.assertEqual(result.report["region_name"], "수원시")
        self.assertEqual(response.kwargs["text"]["format"]["type"], "json_schema")
        self.assertFalse(response.kwargs["store"])
        self.assertIn("공급압력 값이 **높을수록**", response.kwargs["input"][0]["content"])

    def test_reads_only_openai_key_from_dotenv(self):
        with TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text("OTHER_SECRET=do-not-read\nOPENAI_API_KEY=test-key\n", encoding="utf-8")
            self.assertEqual(resolve_openai_api_key(dotenv_path=dotenv_path, environ={}), "test-key")

    def test_rejects_report_that_changes_an_approved_source(self):
        payload = _payload()
        payload["sources"][0]["url"] = "https://unapproved.example/case"
        generator = OpenAITourismReportGenerator(
            _FakeClient(_FakeResponse(payload)), schema_path=Path("config/ai/tourism_gap_report.schema.json"),
        )
        source = screen_case_documents([
            CaseSearchDocument("공식 문서", "https://city.example/case", "강릉시", SourceKind.LOCAL_GOVERNMENT, "성과", "2026-01-01"),
        ])[0]
        with self.assertRaisesRegex(ValueError, "승인된 출처"):
            generator.generate(
                ai_report_context={
                    "region_name": "수원시", "analysis_period": "202509~202608",
                    "priority_order_by_supply_pressure": ["CULTURE_TOURISM"],
                    "content_type_metrics": [{"content_type": "CULTURE_TOURISM", "searches_per_place": 8516.021}],
                }, peer_regions=["강릉시"], approved_sources=[source],
            )

    def test_rejects_a_case_from_an_unapproved_peer_region(self):
        generator = OpenAITourismReportGenerator(
            _FakeClient(_FakeResponse(_payload())),
            schema_path=Path("config/ai/tourism_gap_report.schema.json"),
        )
        source = screen_case_documents([
            CaseSearchDocument("공식 문서", "https://city.example/case", "강릉시", SourceKind.LOCAL_GOVERNMENT, "성과", "2026-01-01"),
        ])[0]
        with self.assertRaisesRegex(ValueError, "허용되지 않은 Peer"):
            generator.generate(
                ai_report_context={
                    "region_name": "수원시", "analysis_period": "202509~202608",
                    "priority_order_by_supply_pressure": ["CULTURE_TOURISM"],
                    "content_type_metrics": [{"content_type": "CULTURE_TOURISM", "searches_per_place": 8516.021}],
                },
                peer_regions=["전주시"],
                approved_sources=[source],
            )

    def test_individual_peer_ratio_at_or_above_one_is_a_gap_candidate(self):
        context = _prepare_context({
            "region_name": "수원시", "analysis_period": "202509~202608",
            "priority_order_by_individual_peer_pressure": ["CULTURE_TOURISM", "EXPERIENCE_TOURISM"],
            "content_type_metrics": [
                {"content_type": "CULTURE_TOURISM", "searches_per_place": 8516.021},
                {"content_type": "EXPERIENCE_TOURISM", "searches_per_place": 5000.0},
            ],
            "peer_supply_pressure_comparison": [
                {"content_type": "CULTURE_TOURISM", "candidate_peer_count": 0},
                {"content_type": "EXPERIENCE_TOURISM", "candidate_peer_count": 1},
            ],
        }, max_gap_types=2)
        self.assertEqual(context["selected_content_types"], ["EXPERIENCE_TOURISM"])

    def test_keeps_relative_supply_evidence_only_for_selected_gap_types(self):
        context = _prepare_context({
            "region_name": "수원시", "analysis_period": "202509~202608",
            "priority_order_by_individual_peer_pressure": ["EXPERIENCE_TOURISM"],
            "content_type_metrics": [{"content_type": "EXPERIENCE_TOURISM", "searches_per_place": 5000.0}],
            "peer_supply_pressure_comparison": [{"content_type": "EXPERIENCE_TOURISM", "candidate_peer_count": 1}],
            "relative_supply_comparison": [
                {"content_type": "EXPERIENCE_TOURISM", "candidate_peer_count": 2},
                {"content_type": "FOOD", "candidate_peer_count": 3},
            ],
        }, max_gap_types=2)
        self.assertEqual(context["relative_supply_comparison"], [{"content_type": "EXPERIENCE_TOURISM", "candidate_peer_count": 2}])


class CaseSourceCollectionTest(unittest.TestCase):
    def test_collects_from_the_first_three_peer_regions(self):
        provider = _RecordingCaseProvider()
        peers = ["성남시", "용인시", "고양시", "안양시", "구리시"]
        sources = collect_approved_case_sources(
            provider, content_types=["CULTURE_TOURISM"], peer_regions=peers,
        )
        self.assertEqual(DEFAULT_MAX_PEER_REGIONS, 3)
        self.assertEqual([query.peer_region for query in provider.queries], peers[:3])
        self.assertEqual(len(sources), 3)


class _FakeResponses:
    def __init__(self, response):
        self.response = response

    def create(self, **kwargs):
        self.response.kwargs = kwargs
        return self.response


class _FakeClient:
    def __init__(self, response):
        self.responses = _FakeResponses(response)


class _FakeResponse:
    def __init__(self, payload):
        self.output_text = json.dumps(payload, ensure_ascii=False)
        self.id = "resp_test"
        self.kwargs = {}


class _RecordingCaseProvider:
    def __init__(self):
        self.queries = []

    def search(self, query):
        self.queries.append(query)
        return [CaseSearchDocument(
            title=f"{query.peer_region} 공식 사례",
            url=f"https://{len(self.queries)}.go.kr/tourism-case",
            publisher=query.peer_region,
            source_kind=SourceKind.LOCAL_GOVERNMENT,
            snippet="공식 운영 근거",
            published_at="2026-01-01",
        )]


def _payload():
    return {
        "region_name": "수원시",
        "analysis_period": "202509~202608",
        "status": "provisional",
        "gap_types": [{
            "content_type": "CULTURE_TOURISM",
            "judgement": "우선 검토 유형",
            "quantitative_evidence": [{"metric": "searches_per_place", "target_value": 8516.021, "comparison": "Peer 비교 전 잠정 순위"}],
            "peer_cases": [{
                "title": "공식 사례", "peer_region": "강릉시", "case_type": "PROGRAM",
                "period": "2026", "operator": "강릉시", "summary": "운영 성과",
                "source_ids": ["source-1"],
            }],
            "applicability_insight": "수원시 여건을 검토한다.",
        }],
        "recommended_actions": [{
            "title": "시범 운영", "rationale": "정량 근거를 먼저 검증한다.",
            "evidence_texts": ["장소당 검색량 8516.021"], "case_titles": [],
        }],
        "sources": [{"source_id": "source-1", "title": "공식 문서", "publisher": "강릉시", "url": "https://city.example/case", "published_at": "2026-01-01"}],
        "limitations": ["파일럿 결과"],
    }


if __name__ == "__main__":
    unittest.main()
