import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from hankkeut_analysis.gap_analyzer.hub_api import HubTourApiClient, HubTourApiError


def _payload(items, result_code="0000"):
    return {
        "response": {
            "header": {
                "resultCode": result_code,
                "resultMsg": "OK" if result_code == "0000" else "ERROR",
            },
            "body": {
                "items": {"item": items} if items else "",
                "totalCount": len(items) if isinstance(items, list) else 1,
            },
        }
    }


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self) -> bytes:
        return self._body


class HubTourApiClientTest(unittest.TestCase):
    def test_extracts_top_five_sorted_by_api_rank(self) -> None:
        client = HubTourApiClient("test-key")
        items = [
            {
                "hubRank": str(rank),
                "hubTatsCd": f"code-{rank}",
                "hubTatsNm": f"관광지 {rank}",
                "hubCtgryLclsNm": "관광자원",
                "hubCtgryMclsNm": "역사관광",
                "hubCtgrySclsNm": "유적지",
                "hubMapX": f"129.{rank}",
                "hubMapY": f"35.{rank}",
            }
            for rank in (3, 1, 5, 2, 4)
        ]

        with patch.object(client, "_request_page", return_value=_payload(items)):
            spots = client.fetch_top_spots(
                base_year_month="202503",
                area_code="47",
                sigungu_code="47130",
            )

        self.assertEqual([spot.rank for spot in spots], [1, 2, 3, 4, 5])
        self.assertEqual(spots[0].name, "관광지 1")
        self.assertEqual(spots[0].tourist_spot_code, "code-1")
        self.assertEqual(spots[0].longitude, 129.1)
        self.assertEqual(spots[0].raw_fields["hubTatsNm"], "관광지 1")

    def test_request_uses_hub_api_parameter_names(self) -> None:
        captured = {}

        def opener(request, *, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return _FakeResponse(
                b'{"response":{"header":{"resultCode":"0000"},'
                b'"body":{"items":"","totalCount":0}}}'
            )

        client = HubTourApiClient(
            "encoded%2Bkey",
            opener=opener,
            timeout_seconds=7,
        )
        spots = client.fetch_top_spots(
            base_year_month="202503",
            area_code="47",
            sigungu_code="47130",
        )

        query = parse_qs(urlparse(captured["url"]).query)
        self.assertEqual(spots, [])
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(query["serviceKey"], ["encoded+key"])
        self.assertEqual(query["baseYm"], ["202503"])
        self.assertEqual(query["areaCd"], ["47"])
        self.assertEqual(query["signguCd"], ["47130"])
        self.assertEqual(query["numOfRows"], ["100"])
        self.assertEqual(query["pageNo"], ["1"])
        self.assertEqual(query["_type"], ["json"])

    def test_uses_response_order_if_rank_is_missing(self) -> None:
        client = HubTourApiClient("test-key")
        items = [
            {"hubTatsCd": "a", "hubTatsNm": "첫 번째"},
            {"hubTatsCd": "b", "hubTatsNm": "두 번째"},
        ]

        with patch.object(client, "_request_page", return_value=_payload(items)):
            spots = client.fetch_top_spots(
                base_year_month="202503",
                area_code="47",
                sigungu_code="47130",
            )

        self.assertEqual([spot.rank for spot in spots], [1, 2])

    def test_filters_category_before_selecting_top_limit(self) -> None:
        client = HubTourApiClient("test-key")
        items = [
            {
                "hubRank": "1",
                "hubTatsNm": "시장",
                "hubCtgryLclsNm": "쇼핑",
            },
            {
                "hubRank": "2",
                "hubTatsNm": "관광지 A",
                "hubCtgryLclsNm": "관광지",
            },
            {
                "hubRank": "3",
                "hubTatsNm": "관광지 B",
                "hubCtgryLclsNm": "관광지",
            },
        ]

        with patch.object(client, "_request_page", return_value=_payload(items)):
            spots = client.fetch_top_spots(
                base_year_month="202503",
                area_code="48",
                sigungu_code="48170",
                limit=2,
                category_large="관광지",
            )

        self.assertEqual([spot.name for spot in spots], ["관광지 A", "관광지 B"])
        self.assertEqual([spot.rank for spot in spots], [2, 3])

    def test_excludes_middle_category_before_selecting_top_limit(self) -> None:
        client = HubTourApiClient("test-key")
        items = [
            {
                "hubRank": "1",
                "hubTatsNm": "시장",
                "hubCtgryLclsNm": "관광지",
                "hubCtgryMclsNm": "쇼핑",
            },
            {
                "hubRank": "2",
                "hubTatsNm": "공원",
                "hubCtgryLclsNm": "관광지",
                "hubCtgryMclsNm": "자연관광",
            },
        ]

        with patch.object(client, "_request_page", return_value=_payload(items)):
            spots = client.fetch_top_spots(
                base_year_month="202503",
                area_code="26",
                sigungu_code="26110",
                limit=1,
                category_large="관광지",
                excluded_category_middle=("쇼핑",),
            )

        self.assertEqual([spot.name for spot in spots], ["공원"])
        self.assertEqual(spots[0].rank, 2)

    def test_includes_only_requested_middle_category(self) -> None:
        client = HubTourApiClient("test-key")
        items = [
            {
                "hubRank": "1",
                "hubTatsNm": "문화마을",
                "hubCtgryLclsNm": "관광지",
                "hubCtgryMclsNm": "문화관광",
            },
            {
                "hubRank": "2",
                "hubTatsNm": "해수욕장",
                "hubCtgryLclsNm": "관광지",
                "hubCtgryMclsNm": "자연관광",
            },
        ]

        with patch.object(client, "_request_page", return_value=_payload(items)):
            spots = client.fetch_top_spots(
                base_year_month="202503",
                area_code="48",
                sigungu_code="48310",
                limit=1,
                category_middle="자연관광",
            )

        self.assertEqual([spot.name for spot in spots], ["해수욕장"])

    def test_accepts_single_item_object(self) -> None:
        items = HubTourApiClient._parse_items(
            _payload({"hubRank": "1", "hubTatsNm": "관광지"})
        )
        self.assertEqual(len(items), 1)

    def test_rejects_invalid_year_month(self) -> None:
        client = HubTourApiClient("test-key")
        with self.assertRaisesRegex(ValueError, "YYYYMM"):
            client.fetch_top_spots(
                base_year_month="2025-03",
                area_code="47",
                sigungu_code="47130",
            )

    def test_rejects_limit_over_service_maximum(self) -> None:
        client = HubTourApiClient("test-key")
        with self.assertRaisesRegex(ValueError, "1부터 100"):
            client.fetch_top_spots(
                base_year_month="202503",
                area_code="47",
                sigungu_code="47130",
                limit=101,
            )

    def test_reports_changed_name_field_instead_of_writing_blank_name(self) -> None:
        client = HubTourApiClient("test-key")
        with patch.object(
            client,
            "_request_page",
            return_value=_payload([{"hubRank": "1", "unknownName": "관광지"}]),
        ):
            with self.assertRaisesRegex(HubTourApiError, "hubTatsNm"):
                client.fetch_top_spots(
                    base_year_month="202503",
                    area_code="47",
                    sigungu_code="47130",
                )

    def test_raises_api_error_for_failed_result_code(self) -> None:
        with self.assertRaisesRegex(HubTourApiError, "중심 관광지 API 오류"):
            HubTourApiClient._parse_items(_payload([], result_code="03"))


if __name__ == "__main__":
    unittest.main()
