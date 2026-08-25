"""산식과 데이터 변환 단위 테스트."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from tourgap.gap import calculate_gap
from tourgap.regions import (
    admin_type,
    build_region_master,
    build_code_rollup,
    parent_city_code,
    parse_address,
)
from tourgap.sources.kto_kor import _ldong_code, normalize_resource
from tourgap.sources.kto_performance import MockPerformanceProvider
from tourgap.sources.sgis import geometry_area_m2, polygon_area_m2
from tourgap.provenance import Provenance


class LdongCodeTest(unittest.TestCase):
    def test_two_plus_three_digits(self) -> None:
        self.assertEqual(_ldong_code("47", "130"), "47130")

    def test_sejong_repeats_full_code_in_both_fields(self) -> None:
        """세종은 두 필드 모두에 5자리를 담아 준다. 이어 붙이면 안 된다."""
        self.assertEqual(_ldong_code("36110", "36110"), "36110")

    def test_missing_values(self) -> None:
        self.assertEqual(_ldong_code("", ""), "")
        self.assertEqual(_ldong_code("47", ""), "")

    def test_normalize_keeps_classification_fields(self) -> None:
        record = normalize_resource(
            {
                "contentid": "123",
                "contenttypeid": "39",
                "title": "테스트",
                "addr1": "경상북도 경주시 북군3길 12-1",
                "lDongRegnCd": "47",
                "lDongSignguCd": "130",
                "lclsSystm1": "FD",
                "lclsSystm2": "FD01",
                "lclsSystm3": "FD010100",
                "mapx": "129.26",
                "mapy": "35.85",
                "modifiedtime": "20251029092454",
            }
        )
        self.assertEqual(record["ldong_code"], "47130")
        self.assertEqual(record["lcls1"], "FD")
        self.assertEqual(record["lcls2"], "FD01")
        self.assertEqual(record["modified_time"], "20251029092454")


class AddressParsingTest(unittest.TestCase):
    def test_plain_city(self) -> None:
        self.assertEqual(
            parse_address("경상북도 경주시 북군3길 12-1"),
            ("경상북도", "경주시", ""),
        )

    def test_general_district_is_detected(self) -> None:
        self.assertEqual(
            parse_address("충청북도 청주시 흥덕구 가경동"),
            ("충청북도", "청주시", "흥덕구"),
        )

    def test_autonomous_district_is_not_a_general_district(self) -> None:
        """광역시 자치구는 그 자체가 기초자치단체다."""
        self.assertEqual(
            parse_address("부산광역시 부산진구 중앙번영로 6"),
            ("부산광역시", "부산진구", ""),
        )

    def test_sejong(self) -> None:
        self.assertEqual(
            parse_address("세종특별자치시 연서면 도신고복로 586"),
            ("세종특별자치시", "세종특별자치시", ""),
        )


class RollupTest(unittest.TestCase):
    def test_general_district_rolls_up_to_parent_city(self) -> None:
        self.assertEqual(parent_city_code("43113"), "43110")
        self.assertEqual(parent_city_code("48125"), "48120")

    def test_county_with_nonzero_last_digit_is_not_rolled_up(self) -> None:
        """증평군(43745)은 끝자리가 0이 아니지만 군이다.

        끝자리만 보고 판단하면 영동군(43740)으로 합쳐지는 버그가 난다.
        주소에 '시 + 구'가 없으므로 그대로 남아야 한다.
        """
        resources = pd.DataFrame(
            {
                "ldong_code": ["43745", "43740", "43113"],
                "address": [
                    "충청북도 증평군 증평읍",
                    "충청북도 영동군 영동읍",
                    "충청북도 청주시 흥덕구 가경동",
                ],
            }
        )
        rollup = build_code_rollup(resources)
        self.assertEqual(rollup["43745"], "43745")
        self.assertEqual(rollup["43740"], "43740")
        self.assertEqual(rollup["43113"], "43110")

    def test_admin_type(self) -> None:
        self.assertEqual(admin_type("경주시", "경상북도"), "시")
        self.assertEqual(admin_type("울릉군", "경상북도"), "군")
        self.assertEqual(admin_type("종로구", "서울특별시"), "자치구")
        self.assertEqual(admin_type("세종특별자치시", "세종특별자치시"), "특별자치시")


class RegionMasterTest(unittest.TestCase):
    def test_tourapi_region_names_override_dirty_address_province(self) -> None:
        resources = pd.DataFrame(
            {
                "region_id": ["12870"],
                "area_code": ["38"],
                "sigungu_code": ["12"],
                "address": ["전남광주통합특별시 신안군 흑산면"],
            }
        )
        with patch(
            "tourgap.regions.load_tourapi_region_lookup",
            return_value={("38", "12"): ("전라남도", "신안군")},
        ):
            result = build_region_master(resources)

        row = result.iloc[0]
        self.assertEqual(row["province_name"], "전라남도")
        self.assertEqual(row["region_name"], "신안군")

    def test_prefix_12_fallback_splits_gwangju_from_jeonnam(self) -> None:
        resources = pd.DataFrame(
            {
                "region_id": ["12210", "12110"],
                "area_code": ["", ""],
                "sigungu_code": ["", ""],
                "address": [
                    "전남광주통합특별시 동구 금남로",
                    "전남광주통합특별시 목포시 영산로",
                ],
            }
        )
        with patch("tourgap.regions.load_tourapi_region_lookup", return_value={}):
            result = build_region_master(resources).set_index("region_id")

        self.assertEqual(result.loc["12210", "province_name"], "광주광역시")
        self.assertEqual(result.loc["12110", "province_name"], "전라남도")


class ShoelaceTest(unittest.TestCase):
    def test_unit_square(self) -> None:
        square = [[[0, 0], [0, 100], [100, 100], [100, 0], [0, 0]]]
        self.assertAlmostEqual(polygon_area_m2(square), 10_000.0)

    def test_hole_is_subtracted(self) -> None:
        outer = [[0, 0], [0, 100], [100, 100], [100, 0], [0, 0]]
        hole = [[20, 20], [20, 40], [40, 40], [40, 20], [20, 20]]
        self.assertAlmostEqual(polygon_area_m2([outer, hole]), 10_000 - 400)

    def test_winding_order_does_not_matter(self) -> None:
        clockwise = [[[0, 0], [100, 0], [100, 100], [0, 100], [0, 0]]]
        self.assertAlmostEqual(polygon_area_m2(clockwise), 10_000.0)

    def test_multipolygon_sums_parts(self) -> None:
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]],
                [[[0, 0], [0, 20], [20, 20], [20, 0], [0, 0]]],
            ],
        }
        self.assertAlmostEqual(geometry_area_m2(geometry), 100 + 400)


class GapTest(unittest.TestCase):
    def _supply(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                # 입력지역: 체험이 적고 숙박이 많다.
                {"region_id": "T", "category": "EX", "share": 0.02},
                {"region_id": "T", "category": "AC", "share": 0.40},
                # benchmark 3곳
                {"region_id": "B1", "category": "EX", "share": 0.10},
                {"region_id": "B1", "category": "AC", "share": 0.10},
                {"region_id": "B2", "category": "EX", "share": 0.12},
                {"region_id": "B2", "category": "AC", "share": 0.12},
                {"region_id": "B3", "category": "EX", "share": 0.14},
                {"region_id": "B3", "category": "AC", "share": 0.08},
            ]
        )

    def test_gap_is_detected_and_ranked(self) -> None:
        result = calculate_gap(
            self._supply(),
            "T",
            ["B1", "B2", "B3"],
            None,
            metric="share",
            categories=("EX", "AC"),
        )
        top = result.iloc[0]
        self.assertEqual(top["category"], "EX")
        self.assertAlmostEqual(top["benchmark_value"], 0.12)
        self.assertAlmostEqual(top["consistency"], 1.0)

    def test_oversupply_is_clipped_to_zero(self) -> None:
        """공급이 남는 카테고리는 공백이 아니다.

        clip하지 않으면 음수 gap에 1보다 작은 수요 계수가 곱해져 부호가
        뒤집히고, 공백이 아닌 항목이 1순위로 올라온다.
        """
        result = calculate_gap(
            self._supply(),
            "T",
            ["B1", "B2", "B3"],
            None,
            metric="share",
            categories=("EX", "AC"),
        )
        accommodation = result[result["category"] == "AC"].iloc[0]
        self.assertEqual(accommodation["supply_gap"], 0.0)
        self.assertEqual(accommodation["gap_score"], 0.0)

    def test_demand_multiplier_stays_neutral_without_data(self) -> None:
        result = calculate_gap(
            self._supply(),
            "T",
            ["B1", "B2", "B3"],
            None,
            metric="share",
            categories=("EX",),
        )
        self.assertEqual(result.iloc[0]["demand_multiplier"], 1.0)
        self.assertEqual(result.iloc[0]["demand_label"], "미적용")

    def test_low_demand_cannot_flip_an_oversupplied_category(self) -> None:
        demand = pd.DataFrame(
            [{"region_id": "T", "category": "AC", "demand_percentile": 0.0}]
        )
        result = calculate_gap(
            self._supply(),
            "T",
            ["B1", "B2", "B3"],
            demand,
            metric="share",
            categories=("EX", "AC"),
        )
        accommodation = result[result["category"] == "AC"].iloc[0]
        self.assertGreaterEqual(accommodation["gap_score"], 0.0)


class MockDeterminismTest(unittest.TestCase):
    def test_same_input_gives_same_values(self) -> None:
        regions = pd.DataFrame({"region_id": ["47130", "11110"]})
        first = MockPerformanceProvider().load(regions, Provenance())
        second = MockPerformanceProvider().load(regions, Provenance())
        pd.testing.assert_frame_equal(first, second)

    def test_marks_itself_as_mock(self) -> None:
        provenance = Provenance()
        MockPerformanceProvider().load(
            pd.DataFrame({"region_id": ["47130"]}), provenance
        )
        self.assertTrue(provenance.has_mock())


if __name__ == "__main__":
    unittest.main()
