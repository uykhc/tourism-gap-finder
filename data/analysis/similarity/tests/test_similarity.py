"""PeerFinder 계약과 feature builder 검증."""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

import pandas as pd

from tourgap.climate import build_climate_features
from tourgap.config import SIMILARITY_FEATURES, get_config, set_config
from tourgap.data_sources import (
    _construct_kma_normals_downloads,
    _download_suffix,
    _extract_1991_2020_row,
    _extract_download_links,
)
from tourgap.feature_builder import validate_feature_table
from tourgap.land_cover import build_land_cover_features
from tourgap.pipeline import _structural_provider
from tourgap.peers import TourgapPeerFinder
from tourgap.sources.structural import MockStructuralProvider
from tourgap.sources.sgis import DEFAULT_API_BASE_URL, LEGACY_API_BASE_URL, _api_url
from tourgap.sources.urbanization import UrbanBoundaryError, _read_dbf


def _feature_frame() -> pd.DataFrame:
    rows = [
        (
            "11110",
            "서울특별시",
            "종로구",
            "자치구",
            10,
            100_000,
            10_000,
            42,
            0.9,
            0,
            0,
            0.2,
            0.01,
            100,
            12,
            28,
            1200,
            200,
            0.05,
            0.10,
            0.50,
        ),
        (
            "11140",
            "서울특별시",
            "중구",
            "자치구",
            11,
            105_000,
            9545.4545,
            43,
            0.92,
            0,
            0,
            0.21,
            0.01,
            110,
            12.2,
            28.1,
            1210,
            205,
            0.05,
            0.11,
            0.49,
        ),
        (
            "11170",
            "서울특별시",
            "용산구",
            "자치구",
            20,
            210_000,
            10_500,
            40,
            0.88,
            0,
            0,
            0.18,
            0.02,
            140,
            12.1,
            28.4,
            1180,
            180,
            0.04,
            0.12,
            0.48,
        ),
        (
            "47130",
            "경상북도",
            "경주시",
            "시",
            1300,
            250_000,
            192.3077,
            47,
            0.35,
            1,
            0,
            0.55,
            0.25,
            600,
            13.0,
            29.0,
            1050,
            8,
            0.20,
            0.16,
            0.25,
        ),
    ]
    columns = [
        "region_id",
        "province_name",
        "region_name",
        "admin_type",
        *SIMILARITY_FEATURES,
    ]
    return pd.DataFrame(rows, columns=columns)


class PeerFinderContractTest(unittest.TestCase):
    def test_contract_columns_and_ordering(self) -> None:
        finder = TourgapPeerFinder(_feature_frame(), min_similarity=0.0)
        peers = finder.find_peers("11110", k=2)

        self.assertEqual(["rank", "region_id", "similarity"], list(peers.columns[:3]))
        self.assertEqual(peers["rank"].tolist(), [1, 2])
        self.assertNotIn("11110", set(peers["region_id"]))
        self.assertTrue(peers["similarity"].between(0, 1).all())
        self.assertTrue(peers["similarity"].is_monotonic_decreasing)

    def test_k_and_min_similarity_are_applied(self) -> None:
        peers = TourgapPeerFinder(
            _feature_frame(),
            default_k=3,
            min_similarity=0.80,
        ).find_peers("11110")

        self.assertLessEqual(len(peers), 3)
        self.assertTrue((peers["similarity"] >= 0.80).all())

    def test_unknown_region_raises(self) -> None:
        finder = TourgapPeerFinder(_feature_frame())
        with self.assertRaises(LookupError):
            finder.find_peers("99999")

    def test_empty_result_still_has_required_columns(self) -> None:
        peers = TourgapPeerFinder(
            _feature_frame(),
            min_similarity=1.01,
        ).find_peers("11110")

        self.assertEqual(list(peers.columns[:3]), ["rank", "region_id", "similarity"])
        self.assertEqual(len(peers), 0)

    def test_pairwise_missing_values_do_not_become_zero(self) -> None:
        frame = _feature_frame()
        frame.loc[1, "forest_ratio"] = pd.NA
        peers = TourgapPeerFinder(frame, min_similarity=0.0).find_peers("11110", k=1)

        self.assertEqual(peers.iloc[0]["region_id"], "11140")
        self.assertGreater(peers.iloc[0]["missing_feature_count"], 0)
        self.assertLess(peers.iloc[0]["feature_weight_used"], 1.0)


class FeatureBuilderValidationTest(unittest.TestCase):
    def test_feature_table_validation(self) -> None:
        validate_feature_table(_feature_frame())

    def test_density_consistency_is_checked(self) -> None:
        frame = _feature_frame()
        frame.loc[0, "population_density"] = 1
        with self.assertRaises(ValueError):
            validate_feature_table(frame)

    def test_ratio_bounds_are_checked(self) -> None:
        frame = _feature_frame()
        frame.loc[0, "forest_ratio"] = 1.2
        with self.assertRaises(ValueError):
            validate_feature_table(frame)


class StructuralProviderPolicyTest(unittest.TestCase):
    def tearDown(self) -> None:
        current = get_config()
        set_config(
            replace(
                current,
                similarity=replace(current.similarity, allow_mock_structural=False),
            )
        )

    def test_structural_mock_is_not_allowed_by_default(self) -> None:
        current = get_config()
        set_config(
            replace(
                current,
                similarity=replace(current.similarity, allow_mock_structural=False),
            )
        )
        with patch.dict(
            "os.environ",
            {
                "SGIS_CONSUMER_KEY": "",
                "SGIS_CONSUMER_SECRET": "",
                "TOURGAP_ALLOW_MOCK_STRUCTURAL": "",
            },
            clear=False,
        ):
            with self.assertRaises(RuntimeError):
                _structural_provider()

    def test_structural_mock_requires_explicit_opt_in(self) -> None:
        current = get_config()
        set_config(
            replace(
                current,
                similarity=replace(current.similarity, allow_mock_structural=True),
            )
        )
        with patch.dict(
            "os.environ",
            {
                "SGIS_CONSUMER_KEY": "",
                "SGIS_CONSUMER_SECRET": "",
                "TOURGAP_ALLOW_MOCK_STRUCTURAL": "",
            },
            clear=False,
        ):
            self.assertIsInstance(_structural_provider(), MockStructuralProvider)


class SgisEndpointTest(unittest.TestCase):
    def test_default_endpoint_uses_current_sgis_docs_host(self) -> None:
        with patch.dict("os.environ", {"SGIS_API_BASE_URL": ""}, clear=False):
            self.assertEqual(
                _api_url("auth/authentication.json"),
                f"{DEFAULT_API_BASE_URL}/auth/authentication.json",
            )

    def test_endpoint_can_be_forced_to_legacy_host(self) -> None:
        with patch.dict(
            "os.environ", {"SGIS_API_BASE_URL": LEGACY_API_BASE_URL}, clear=False
        ):
            self.assertEqual(
                _api_url("auth/authentication.json"),
                f"{LEGACY_API_BASE_URL}/auth/authentication.json",
            )


class UrbanBoundaryDbfTest(unittest.TestCase):
    def test_rejects_truncated_dbf(self) -> None:
        with self.assertRaises(UrbanBoundaryError):
            _read_dbf(b"not a dbf")


class KmaNormalsDownloadParserTest(unittest.TestCase):
    def test_extract_1991_2020_fileset_links(self) -> None:
        html = """
        <table>
          <tr><th>1981~2010 평년값</th><td><a href="/old_daily.zip">다운로드</a></td></tr>
          <tr>
            <th>1991~2020 평년값</th>
            <td><a href="/daily.zip">다운로드</a></td>
            <td><a href="/monthly.zip">다운로드</a></td>
            <td><a href="/seasonal.zip">다운로드</a></td>
            <td><a href="/annual.zip">다운로드</a></td>
          </tr>
        </table>
        """
        row = _extract_1991_2020_row(html)
        links = _extract_download_links(row, "https://data.kma.go.kr/page.do")

        self.assertEqual(links["daily"], "https://data.kma.go.kr/daily.zip")
        self.assertEqual(links["annual"], "https://data.kma.go.kr/annual.zip")

    def test_construct_kma_downloads_from_official_js_pattern(self) -> None:
        html = """
        function fileDown(inyear, indata1, indata2){
          var fileName = 'average30yearsKorea_'+inyear+'_'+indata1+ext;
          $("#downForm").attr("action", "/download/downloadNormDataFile.do").submit();
        }
        """
        links = _construct_kma_normals_downloads(html)

        self.assertIn("annual", links)
        self.assertIn(
            "distFileName=average30yearsKorea_1991_year.xlsx", links["annual"]
        )
        self.assertIn("realFileName=", links["annual"])

    def test_download_suffix_prefers_dist_file_name(self) -> None:
        suffix = _download_suffix(
            "https://data.kma.go.kr/download/downloadNormDataFile.do"
            "?distFileName=average30yearsKorea_1991_year.xlsx"
        )

        self.assertEqual(suffix, ".xlsx")


class ClimateFeatureBuilderTest(unittest.TestCase):
    def test_build_region_climate_features_with_nearest_stations(self) -> None:
        regions = pd.DataFrame(
            {
                "region_id": ["11110"],
                "province_name": ["서울특별시"],
                "region_name": ["종로구"],
            }
        )
        centroids = pd.DataFrame(
            {
                "region_id": ["11110"],
                "centroid_lon": [127.0],
                "centroid_lat": [37.5],
            }
        )
        stations = pd.DataFrame(
            {
                "station_id": ["1", "2", "3"],
                "station_name": ["A", "B", "C"],
                "longitude": [127.0, 127.1, 128.0],
                "latitude": [37.5, 37.5, 38.0],
                "annual_mean_temperature": [10.0, 20.0, 30.0],
                "annual_temperature_range": [25.0, 26.0, 27.0],
                "annual_precipitation": [1000.0, 1100.0, 1200.0],
            }
        )

        result = build_climate_features(regions, centroids, stations, nearest_k=2)

        self.assertEqual(result.iloc[0]["region_id"], "11110")
        self.assertAlmostEqual(result.iloc[0]["annual_mean_temperature"], 10.0)
        self.assertIn('"1"', result.iloc[0]["climate_station_ids"])
        self.assertIn(
            "nearest_2_inverse_distance_squared",
            result.iloc[0]["climate_interpolation_method"],
        )


class LandCoverFeatureBuilderTest(unittest.TestCase):
    def test_direct_match_computes_ratios(self) -> None:
        regions = pd.DataFrame(
            {
                "region_id": ["11110"],
                "province_name": ["서울특별시"],
                "region_name": ["종로구"],
            }
        )
        source = pd.DataFrame(
            {
                "province_name": ["서울특별시"],
                "source_region_name": ["종로구"],
                "total_area_m2": [100.0],
                "forest_area_m2": [40.0],
                "farmland_area_m2": [10.0],
            }
        )

        result = build_land_cover_features(regions, source, overrides=pd.DataFrame())

        self.assertEqual(result.iloc[0]["land_cover_match_method"], "direct")
        self.assertAlmostEqual(result.iloc[0]["forest_ratio"], 0.4)
        self.assertAlmostEqual(result.iloc[0]["farmland_ratio"], 0.1)

    def test_general_district_rows_are_rolled_up_to_parent_city(self) -> None:
        regions = pd.DataFrame(
            {
                "region_id": ["41110"],
                "province_name": ["경기도"],
                "region_name": ["수원시"],
            }
        )
        source = pd.DataFrame(
            {
                "province_name": ["경기도", "경기도"],
                "source_region_name": ["수원시 장안구", "수원시 권선구"],
                "total_area_m2": [100.0, 300.0],
                "forest_area_m2": [10.0, 90.0],
                "farmland_area_m2": [40.0, 20.0],
            }
        )

        result = build_land_cover_features(regions, source, overrides=pd.DataFrame())

        self.assertEqual(
            result.iloc[0]["land_cover_match_method"], "general_district_rollup"
        )
        self.assertAlmostEqual(result.iloc[0]["forest_ratio"], 0.25)
        self.assertAlmostEqual(result.iloc[0]["farmland_ratio"], 0.15)

    def test_weighted_proxy_uses_area_weighted_sources(self) -> None:
        regions = pd.DataFrame(
            {
                "region_id": ["99999"],
                "province_name": ["테스트도"],
                "region_name": ["신설구"],
            }
        )
        source = pd.DataFrame(
            {
                "province_name": ["테스트도", "테스트도"],
                "source_region_name": ["원구A", "원구B"],
                "total_area_m2": [100.0, 200.0],
                "forest_area_m2": [20.0, 100.0],
                "farmland_area_m2": [10.0, 20.0],
            }
        )
        overrides = pd.DataFrame(
            {
                "region_id": ["99999", "99999"],
                "region_name": ["신설구", "신설구"],
                "sgis_province": ["테스트도", "테스트도"],
                "sgis_municipality": ["원구A", "원구B"],
                "weight": [0.5, 1.0],
            }
        )

        result = build_land_cover_features(regions, source, overrides=overrides)

        self.assertEqual(result.iloc[0]["land_cover_match_method"], "weighted_proxy")
        self.assertAlmostEqual(result.iloc[0]["forest_ratio"], 110.0 / 250.0)
        self.assertAlmostEqual(result.iloc[0]["farmland_ratio"], 25.0 / 250.0)


if __name__ == "__main__":
    unittest.main()
