import unittest
from unittest.mock import patch

from hankkeut_analysis.gap_analyzer.tour_api import TourApiClient, TourApiError


def _payload(items, total_count, result_code="0000"):
    return {
        "response": {
            "header": {
                "resultCode": result_code,
                "resultMsg": "OK" if result_code == "0000" else "ERROR",
            },
            "body": {
                "items": {"item": items} if items else "",
                "totalCount": total_count,
            },
        }
    }


class TourApiClientTest(unittest.TestCase):
    def test_fetches_all_pages_and_deduplicates_content_id(self) -> None:
        client = TourApiClient("test-key", page_size=2)
        first_page = _payload(
            [
                {
                    "contentid": "1",
                    "contenttypeid": "12",
                    "title": "관광지",
                    "mapx": "127.1",
                    "mapy": "37.1",
                },
                {
                    "contentid": "2",
                    "contenttypeid": "39",
                    "title": "음식점",
                },
            ],
            total_count=3,
        )
        second_page = _payload(
            [
                {
                    "contentid": "2",
                    "contenttypeid": "39",
                    "title": "수정된 음식점",
                }
            ],
            total_count=3,
        )

        with patch.object(
            client,
            "_request_page",
            side_effect=[first_page, second_page],
        ) as request_page:
            resources = client.fetch_region_resources(
                area_code="1",
                sigungu_code="2",
            )

        self.assertEqual(request_page.call_count, 2)
        self.assertEqual(len(resources), 2)
        self.assertEqual(resources[0].content_type_id, 12)
        self.assertEqual(resources[0].longitude, 127.1)
        self.assertEqual(resources[1].title, "수정된 음식점")

    def test_accepts_single_item_object(self) -> None:
        items, total_count = TourApiClient._parse_page(
            _payload({"contentid": "1", "contenttypeid": "14"}, 1)
        )

        self.assertEqual(total_count, 1)
        self.assertEqual(len(items), 1)

    def test_fetches_area_wide_resources_without_sigungu_code(self) -> None:
        client = TourApiClient("test-key")
        payload = _payload(
            [{"contentid": "1", "contenttypeid": "12"}],
            total_count=1,
        )

        with patch.object(
            client,
            "_request_page",
            return_value=payload,
        ) as request_page:
            resources = client.fetch_region_resources(area_code="6")

        self.assertEqual(len(resources), 1)
        request_page.assert_called_once_with(
            area_code="6",
            sigungu_code=None,
            page_number=1,
        )

    def test_accepts_empty_items_string(self) -> None:
        items, total_count = TourApiClient._parse_page(_payload([], 0))

        self.assertEqual(items, [])
        self.assertEqual(total_count, 0)

    def test_fetches_sigungu_code_names(self) -> None:
        client = TourApiClient("test-key")
        payload = _payload(
            [
                {"code": "1", "name": "첫째시"},
                {"code": "2", "name": "둘째군"},
            ],
            total_count=2,
        )

        with patch.object(
            client,
            "_request_code_page",
            return_value=payload,
        ) as request_page:
            codes = client.fetch_sigungu_codes(area_code="36")

        self.assertEqual(codes, {"1": "첫째시", "2": "둘째군"})
        request_page.assert_called_once_with(area_code="36", page_number=1)

    def test_raises_api_error_for_failed_result_code(self) -> None:
        with self.assertRaisesRegex(TourApiError, "TourAPI 오류"):
            TourApiClient._parse_page(
                _payload([], 0, result_code="03")
            )


if __name__ == "__main__":
    unittest.main()
