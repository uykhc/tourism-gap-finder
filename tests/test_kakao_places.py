import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from hankkeut_analysis.kakao_places.client import KakaoLocalApiError, KakaoLocalClient
from hankkeut_analysis.kakao_places.models import KakaoCategoryCollection, KakaoPlace
from hankkeut_analysis.kakao_places.boundary_builder import build_gyeonggi_sigun_boundaries
from hankkeut_analysis.kakao_places.region_collector import KakaoRegionCollector, point_in_multipolygon
from hankkeut_analysis.kakao_places.region_cli import _checkpoint_name, _load_checkpoint, _write_json
from hankkeut_analysis.tourism_data.config import resolve_kakao_rest_api_key


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class KakaoLocalClientTest(unittest.TestCase):
    def test_collects_pages_deduplicates_and_marks_truncation(self):
        requests = []

        def opener(request, timeout):
            requests.append(request)
            page = parse_qs(urlparse(request.full_url).query)["page"][0]
            documents = [{"id": "1", "place_name": "A", "x": "127.1", "y": "37.5", "distance": "100"}]
            if page == "2":
                documents.append({"id": "2", "place_name": "B", "x": "127.2", "y": "37.6", "distance": "200"})
            return _Response({"meta": {"total_count": 100, "pageable_count": 45, "is_end": page == "2"}, "documents": documents})

        result = KakaoLocalClient("test-key", opener=opener).collect_category_nearby(category_group_code="CT1", longitude=127.0, latitude=37.0)

        self.assertEqual(result.collected_count, 2)
        self.assertTrue(result.result_truncated)
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0].get_header("Authorization"), "KakaoAK test-key")
        query = parse_qs(urlparse(requests[0].full_url).query)
        self.assertEqual(query["x"], ["127.0"])
        self.assertEqual(query["y"], ["37.0"])
        self.assertEqual(query["radius"], ["2000"])

    def test_collects_category_in_rectangle(self):
        requests = []

        def opener(request, timeout):
            requests.append(request)
            return _Response({"meta": {"total_count": 1, "pageable_count": 1, "is_end": True}, "documents": [{"id": "1", "place_name": "A", "x": "127.1", "y": "37.5"}]})

        result = KakaoLocalClient("test-key", opener=opener).collect_category_in_rectangle(category_group_code="CT1", west=127.0, south=37.0, east=127.2, north=37.6)

        self.assertEqual(result.collected_count, 1)
        self.assertEqual(parse_qs(urlparse(requests[0].full_url).query)["rect"], ["127.0,37.0,127.2,37.6"])

    def test_rejects_unsupported_category(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            KakaoLocalClient("test-key").collect_category_nearby(category_group_code="BAD", longitude=127.0, latitude=37.0)

    def test_rejects_invalid_place_coordinates(self):
        def opener(*_, **__):
            return _Response({"meta": {"total_count": 1, "pageable_count": 1, "is_end": True}, "documents": [{"id": "1", "place_name": "A", "x": "bad", "y": "37.0"}]})

        with self.assertRaises(KakaoLocalApiError):
            KakaoLocalClient("test-key", opener=opener).collect_category_nearby(category_group_code="CT1", longitude=127.0, latitude=37.0)


class KakaoKeyConfigTest(unittest.TestCase):
    def test_resolves_kakao_key(self):
        self.assertEqual(resolve_kakao_rest_api_key(environ={"KAKAO_REST_API_KEY": "kakao-key"}), "kakao-key")


class KakaoRegionCollectorTest(unittest.TestCase):
    def test_subdivides_truncated_tiles_filters_boundary_and_deduplicates(self):
        class Client:
            def __init__(self):
                self.calls = 0

            def collect_category_in_rectangle(self, **_):
                self.calls += 1
                truncated = self.calls == 1
                places = (
                    KakaoPlace("inside", "Inside", "CT1", "문화시설", "", "", "", 0.25, 0.25, "", "", None),
                    KakaoPlace("outside", "Outside", "CT1", "문화시설", "", "", "", 2.0, 2.0, "", "", None),
                )
                return KakaoCategoryCollection("CT1", "문화시설", 0.5, 0.5, 0, 100 if truncated else 2, 45 if truncated else 2, 2, truncated, places)

        geometry = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}
        result = KakaoRegionCollector(Client()).collect_category(region_name="테스트시", geometry=geometry, category_group_code="CT1", initial_tile_meters=200_000, minimum_tile_meters=1)

        self.assertEqual(result.collected_count, 1)
        self.assertEqual(result.searched_tile_count, 5)
        self.assertEqual(result.truncated_tile_count, 0)
        self.assertEqual(result.address_unverified_count, 1)

    def test_point_in_multipolygon_excludes_hole(self):
        polygons = (
            (
                ((0, 0), (4, 0), (4, 4), (0, 4), (0, 0)),
                ((1, 1), (3, 1), (3, 3), (1, 3), (1, 1)),
            ),
        )
        self.assertTrue(point_in_multipolygon((0.5, 0.5), polygons))
        self.assertFalse(point_in_multipolygon((2, 2), polygons))


class GyeonggiBoundaryBuilderTest(unittest.TestCase):
    def test_collapses_city_districts_into_one_city(self):
        source = {
            "type": "FeatureCollection",
            "features": [
                _feature("수원시 장안구", "41111", [[[127.0, 37.0], [127.1, 37.0], [127.1, 37.1], [127.0, 37.0]]]),
                _feature("수원시 권선구", "41113", [[[127.1, 37.0], [127.2, 37.0], [127.2, 37.1], [127.1, 37.0]]]),
                _feature("가평군", "41820", [[[127.2, 37.0], [127.3, 37.0], [127.3, 37.1], [127.2, 37.0]]]),
            ],
        }
        result = build_gyeonggi_sigun_boundaries(source)
        self.assertEqual(result["metadata"]["region_count"], 2)
        suwon = next(feature for feature in result["features"] if feature["properties"]["region_name"] == "수원시")
        self.assertEqual(suwon["properties"]["source_sgg_codes"], ["41111", "41113"])
        self.assertEqual(len(suwon["geometry"]["coordinates"]), 2)


class RegionCheckpointTest(unittest.TestCase):
    def test_checkpoint_round_trip_and_invalid_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / _checkpoint_name(1, "수원시", "CT1")
            _write_json(path, {"region_name": "수원시", "category_group_code": "CT1", "collected_count": 2, "places": []})
            self.assertEqual(_load_checkpoint(path)["collected_count"], 2)
            path.write_text("not-json", encoding="utf-8")
            self.assertIsNone(_load_checkpoint(path))


def _feature(sggnm, sgg, coordinates):
    return {"type": "Feature", "properties": {"sggnm": sggnm, "sgg": sgg}, "geometry": {"type": "Polygon", "coordinates": coordinates}}


if __name__ == "__main__":
    unittest.main()
