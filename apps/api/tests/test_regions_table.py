"""전국 시군구 표.

이 표가 틀리면 모든 엔드포인트가 조용히 404가 되므로, 로드 시점에 크게
실패하는지까지 확인한다.
"""

from __future__ import annotations

import unittest

from apps.api.app.schemas.common import AdministrativeType, RegionRef
from apps.api.app.services import regions as region_table


class RegionTableTest(unittest.TestCase):
    def test_loads_every_nationwide_region_with_a_valid_five_digit_code(self):
        rows = region_table.all_regions()
        self.assertEqual(len(rows), 230)
        self.assertEqual(region_table.region_total(), 230)
        ids = [row["region_id"] for row in rows]
        self.assertEqual(len(set(ids)), len(ids), "region_id는 중복될 수 없다")
        for row in rows:
            self.assertRegex(row["region_id"], r"^\d{5}$")
            self.assertTrue(row["province_name"])
            self.assertTrue(row["region_name"])

    def test_every_administrative_type_is_a_declared_enum_value(self):
        found = {row["administrative_type"] for row in region_table.all_regions()}
        allowed = {item.value for item in AdministrativeType}
        self.assertEqual(found - allowed, set(), "표에 enum에 없는 행정유형이 있다")

    def test_sejong_validates_through_the_response_schema(self):
        # 세종은 '특별자치시' 하나뿐이라, enum에서 빠지면 이 지역만 500이 된다.
        sejong = region_table.find_region("36110")
        self.assertIsNotNone(sejong)
        reference = RegionRef.model_validate(sejong)
        self.assertEqual(reference.administrative_type, AdministrativeType.SPECIAL_SELF_GOVERNING_CITY)

    def test_province_counts_add_up_to_the_region_total(self):
        provinces = region_table.provinces()
        self.assertEqual(len(provinces), 17)
        self.assertEqual(
            sum(item["region_count"] for item in provinces), region_table.region_total()
        )

    def test_a_duplicated_region_name_resolves_only_when_it_is_unambiguous(self):
        # 중구는 5곳이다. 이름만으로 고르면 다른 지역의 값이 섞인다.
        self.assertIsNone(region_table.resolve_by_name("중구"))
        self.assertEqual(region_table.resolve_by_name("중구", province_name="서울특별시"), "11140")
        self.assertEqual(
            region_table.resolve_by_name("중구", candidate_region_ids={"26110"}), "26110"
        )
        self.assertIsNone(
            region_table.resolve_by_name("중구", candidate_region_ids={"26110", "11140"}),
            "후보가 둘이면 고르지 않아야 한다",
        )
        self.assertIsNone(region_table.resolve_by_name("없는시"))
        self.assertEqual(region_table.resolve_by_name("경주시"), "47130")

    def test_tour_api_codes_are_absent_rather_than_borrowed(self):
        self.assertEqual(region_table.tour_api_code("47130"), ("35", "2"))
        # 2026년 개편으로 신설된 구는 TourAPI 목록에 없다. 옛 자치구 코드를
        # 빌려 쓰면 서로 다른 지역에 같은 수요값이 붙는다.
        self.assertIsNone(region_table.tour_api_code("28125"))
        self.assertIsNone(region_table.tour_api_code("99999"))


if __name__ == "__main__":
    unittest.main()
