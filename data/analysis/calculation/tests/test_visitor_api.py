import unittest

from hankkeut_calculation.tourism_data.visitor_api import (
    DailyRegionalVisitor,
    VisitorApiError,
    _to_daily_visitor,
)


class VisitorRecordTest(unittest.TestCase):
    def test_keeps_the_region_code_the_response_already_carries(self):
        # 응답의 signguCode는 법정동 시군구 코드 5자리이고 계약의 region_id와
        # 같은 값이다. 이 값을 버리면 지역명으로 조인하게 되고, 같은 응답 안에
        # 중구가 5곳 있어 서로 다른 지역이 한 덩어리로 합산된다.
        record = _to_daily_visitor({
            "signguCode": "11140", "signguNm": "중구", "baseYmd": "20260701",
            "touDivNm": "현지인(a)", "touNum": "162015.0",
        })
        self.assertEqual(record.region_id, "11140")
        self.assertEqual(record.region_name, "중구")
        self.assertEqual(record.visitor_count, 162015.0)

    def test_a_response_without_the_code_still_parses(self):
        record = _to_daily_visitor({
            "signguNm": "종로구", "baseYmd": "20260701", "touNum": "100",
        })
        self.assertEqual(record.region_id, "")
        self.assertEqual(record.region_name, "종로구")

    def test_the_code_field_is_optional_on_the_record(self):
        record = DailyRegionalVisitor("20260701", "종로구", 1.0)
        self.assertEqual(record.region_id, "")

    def test_a_response_missing_the_visitor_count_still_fails(self):
        with self.assertRaises(VisitorApiError):
            _to_daily_visitor({"signguCode": "11110", "signguNm": "종로구", "baseYmd": "20260701"})


if __name__ == "__main__":
    unittest.main()
